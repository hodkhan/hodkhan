import json
from io import BytesIO
import re
import requests
import feedparser
import markdownify
from bs4 import BeautifulSoup
from fastapi import HTTPException, Depends, APIRouter
from readability import Document
from typing import Union
from datetime import datetime
from utils.utils import new_uuid
import db
from utils.base_models import App, MsgCreate
from .msgs import create_msg
from utils.utils import auth, get_role_details
from PIL import Image
from colorthief import ColorThief
import colorsys


def rgb_to_hsl(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (int(h * 360), int(s * 100), int(l * 100))


def get_dominant_color_hsl(image_path):
    color_thief = ColorThief(image_path)
    dominant_color_rgb = color_thief.get_color(quality=1)
    dominant_color_hsl = rgb_to_hsl(dominant_color_rgb)
    print(dominant_color_hsl)
    return json.loads(dominant_color_hsl)


def convert_date(date_str: str) -> str:
    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')


def clean_caption(caption: str) -> str:
    soup = BeautifulSoup(caption, 'html.parser')
    for img in soup.find_all('img'):
        img.decompose()
    for a in soup.find_all('a'):
        del a['href']
    caption = str(soup).replace('<a ', '<p ').replace('</a>', '</p>')
    return html_to_text(caption).split("\n")[0].strip()


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


def minify_html(html: str) -> str:
    search = [r'\>[^\S ]+', r'[^\S ]+\<', r'(\s)+', '']
    replace = ['>', '<', r'\1']
    for s, r in zip(search, replace):
        html = re.sub(s, r, html)
    return html


def fetch_and_process_html(url: str) -> str:
    headers = {'User-Agent': 'Ruzify/1.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=404, detail=f"Failed to fetch content: {e}")

    html = response.text
    video_urls = extract_video_urls(html)
    video, is_frame = determine_primary_video(video_urls, html)
    doc = Document(html)
    main_content = doc.summary()
    soup = BeautifulSoup(main_content, 'html.parser')
    main_content = str(soup)
    title = doc.title()
    code = f"""
        <!doctype html>
        <html lang="fa">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>"""
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
        </body>
        </html>
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


router = APIRouter()


@router.post("/crawl")
async def crawl(chat_id: str, app: App = Depends(auth)):
    try:
        role = await get_role_details(app['userId'], chat_id, 0, app)
        if not role or role['type'] != 1:
            raise HTTPException(status_code=403, detail="Bot does not have permission to crawl this chat")

        feeds = role['config']['bot']['feeds']
        if not feeds:
            raise HTTPException(status_code=404, detail="No feed URLs found in role config")

        posts = []
        for feed in feeds:
            if feed['type'] == 0:
                feed_content = feedparser.parse(feed['url'])
                for entry in feed_content.entries[::-1]:
                    title = entry.title
                    old_post = db.run('SELECT * FROM msgs WHERE JSON_UNQUOTE(JSON_EXTRACT(config, "$.title")) = %s',
                                      [title])
                    if not old_post:
                        caption = clean_caption(entry.summary)
                        cover_url = save_cover_image(entry.link)
                        if cover_url is not None:
                            attachments = {'type': 0, 'url': "{{baseUrl}}/" + cover_url}
                        preview_text = get_first_text_from_url(entry.link)
                        html_content = fetch_and_process_html(entry.link)
                        markdown_content = markdownify.markdownify(html_content, heading_style="ATX")
                        markdown_content.strip()
                        post_uuid = new_uuid()
                        post_filename = f"uploads/{post_uuid}.md"
                        with open(post_filename, "w", encoding="utf-8") as file:
                            file.write(markdown_content)
                        creators = '، '.join(
                            [entry.get('author', entry.get('dc_creator', entry.get('contributor', '')))])
                        if creators == '':
                            creators = 'تحریریه ' + role['chatDetails']['config']['name']
                        msg_config = {
                            'title': title,
                            'caption': caption,
                            'url': entry.link,
                            'creators': creators,
                            'previewText': preview_text,
                            'previewUrl': "{{baseUrl}}/preview/" + post_uuid + ".md",
                            'vectorCoordinate': 0,
                            'attachments': [attachments],
                            'estimatedReadingTime': estimate_reading_time(markdown_content)
                        }
                        if feed['name']:
                            msg_config['source'] = feed['name']
                        msg_create = MsgCreate(
                            type=1,
                            config=msg_config,
                            chatId=chat_id
                        )
                        msg = await create_msg(msg_create, app)
                        posts.append(msg)
        return posts[::-1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during crawling: {e}")