import re
from http.client import HTTPException
from readability import Document
from django.core.management.base import BaseCommand
import requests
from bs4 import BeautifulSoup
import feedparser


def get_cover(url: str):
    try:
        response = requests.get(url, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        og_image = soup.find('meta', property='og:image')
        if og_image and 'content' in og_image.attrs:
            return og_image['content']
        cover = soup.find('img')
        if cover and 'src' in cover.attrs:
            return cover['src']
    except requests.RequestException as e:
        print(f"Error fetching main image: {e}")
    return None


def estimate_reading_time(markdown_string, words_per_minute=250):
    plain_text = re.sub(r'\*\*.*?\*\*|__.*?__|`.*?`|!$$.*?$$$.*?$|$$.*?$$$.*?$', '', markdown_string)
    plain_text = re.sub(r'\#\s*|\*\s*|\-\s*', '', plain_text)
    plain_text = re.sub(r'\s+', ' ', plain_text)
    plain_text = plain_text.strip()
    word_count = len(plain_text.split())
    reading_time_minutes = word_count / words_per_minute
    return reading_time_minutes


def html_to_text(html: str) -> str:
    return BeautifulSoup(html, 'html.parser').get_text()


def get_first_text_from_url(url: str) -> str:
    headers = {'User-Agent': 'Ruzify/1.0'}
    response = requests.get(url, headers=headers, allow_redirects=True)
    if response.status_code != 200:
        return ""
    html = response.text
    doc = Document(html)
    main_content = doc.summary()
    soup = BeautifulSoup(main_content, 'html.parser')
    first_text = soup.get_text(separator=' ', strip=True).split('.')
    return '. '.join(first_text[:4]).replace('[...]', '')


def fetch_and_process_html(url: str) -> str:
    headers = {'User-Agent': 'Ruzify/1.0'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html = response.text
    video_urls = extract_video_urls(html)
    video, is_frame = determine_primary_video(video_urls, html)
    doc = Document(html)
    main_content = doc.summary()
    soup = BeautifulSoup(main_content, 'html.parser')
    main_content = str(soup)
    title = doc.title()
    code = f""""""
    if video:
        if is_frame:
            code += f"""
                        <div id="iframe">
                            <iframe style="background: rgba(0,0,0,.1)" src="{video}" frameborder="0" allowfullscreen></iframe>
                        </div>
                        """
        else:
            code += f"""
                        <video controls>
                            <source src="{video}">
                        </video>
                        """
    else:
        soup = BeautifulSoup(html, 'lxml')
        og_image = soup.find('meta', property='og:image')
        cover_image = og_image['content'] if og_image and 'content' in og_image.attrs else None
        if cover_image:
            code += f"""<img src="{cover_image}" alt="Cover Image" style="max-width: 100%; height: auto;">"""
        else:
            main_image = soup.find('img')
            if main_image and 'src' in main_image.attrs:
                cover_image = main_image['src']
                code += f"""<img src="{cover_image}" alt="Cover Image" style="max-width: 100%; height: auto;">"""
    code += f"""{main_content}
        """
    return minify_html(code)


def extract_video_urls(html: str):
    video_urls = []
    iframes = re.findall(r'<iframe.*?src="(.*?)"', html)
    videos = re.findall(r'<source.*?src="(.*?)"', html)
    for iframe in iframes:
        if '/embed' in iframe:
            video_urls.append(iframe)
    video_urls.extend(videos)
    aparat_urls = re.findall(r'"https://www.aparat.com/embed/(.*?)"', html)
    for aparat_url in aparat_urls:
        video_urls.append(
            'https://www.aparat.com/video/video/embed/videohash/' + aparat_url.split('?')[0] + '/vt/frame')
    return video_urls


def minify_html(html: str) -> str:
    search = [r'\>[^\S ]+', r'[^\S ]+\<', r'(\s)+', '']
    replace = ['>', '<', r'\1']
    for s, r in zip(search, replace):
        html = re.sub(s, r, html)
    return html


def determine_primary_video(video_urls, html):
    if not video_urls:
        return '', 0
    if len(video_urls) == 1:
        return video_urls[0], 1 if '/embed' in video_urls[0] else 0
    min_offset = float('inf')
    primary_video = ''
    for url in video_urls:
        offset = html.find(url)
        if offset != -1 and offset < min_offset:
            min_offset = offset
            primary_video = url
    return primary_video, 1 if '/embed' in primary_video else 0


def clean_caption(caption: str) -> str:
    soup = BeautifulSoup(caption, 'html.parser')
    for img in soup.find_all('img'):
        img.decompose()
    for a in soup.find_all('a'):
        del a['href']
    caption = str(soup).replace('<a ', '<p ').replace('</a>', '</p>')
    return html_to_text(caption).split("\n")[0].strip()


class Command(BaseCommand):
    help = 'Small crawler utilities: fetch metadata or list feed titles.'

    def add_arguments(self, parser):
        parser.add_argument('--fetch', type=str, help='Fetch OG image for URL')
        parser.add_argument(
            '--feed', type=str, help='List titles from an RSS/Atom feed URL'
        )

    def handle(self, *args, **options):
        fetch = options.get('fetch')
        feed = options.get('feed')

        if fetch:
            img, err = get_cover(fetch)
            if err:
                self.stdout.write(self.style.ERROR(err))
                return
            if img:
                self.stdout.write(self.style.SUCCESS(f'OG image: {img}'))
            else:
                self.stdout.write('No OG image found')
            return

        if feed:
            parsed = feedparser.parse(feed)
            for e in parsed.entries[:20]:
                self.stdout.write(f'- {e.title}')
            return

        self.stdout.write('No action specified. Use --fetch or --feed')
