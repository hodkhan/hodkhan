import uuid

import markdownify
from django.core.management.base import BaseCommand

from app.management.commands.crawler_tool import get_cover, clean_caption, get_first_text_from_url, \
    fetch_and_process_html
from app.models import Feed, Article
import feedparser
import requests
import time
import re
import os
from hazm import Normalizer, word_tokenize
import pickle
import fasttext


class Command(BaseCommand):
    help = 'Crawl feeds from the Feed model and create Article rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int,
            help='Optional max number of entries per feed to process',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')

        # Load models/vectorizers if available; be tolerant if missing in dev
        vectorizer = None
        model = None
        try:
            with open('app/management/commands/models/hazm/vectorizer.pkl') as f:
                vectorizer = pickle.load(f)
            with open('app/management/commands/models/hazm/logistic_regression.pkl') as f:
                model = pickle.load(f)
        except Exception:
            self.stdout.write(
                'Warning: classifier/vectorizer not available; '
                'classification will be skipped'
            )

        fasttext_model = None
        fasttext_model = fasttext.load_model(
            'app/management/commands/models/fasttext/cc.fa.300.bin'
        )

        def vectorize_text(text):
            if not fasttext_model:
                return None
            return fasttext_model.get_sentence_vector(text)

        def classifier(text):
            if not vectorizer or not model:
                return None
            normalizer = Normalizer()
            new_text_processed = ' '.join(
                word_tokenize(normalizer.normalize(text))
            )
            new_text_tfidf = vectorizer.transform([new_text_processed])
            predicted_category = model.predict(new_text_tfidf)
            return predicted_category[0]

        def extract_entry_data(entry, source):
            # Keep a subset of legacy extraction logic; best-effort
            try:
                if source == 'Zoomit':
                    site_id = re.findall(r"\/\d{6,}", entry.id)[0][1:]
                    pub_date = time.mktime(entry.published_parsed)
                    abstract = re.findall(
                        r"\<p\>.*\<\/p\>", entry.summary
                    )[0][3:-4]
                    image = re.findall(
                        r'src="https://.*q=\d+"', entry.summary
                    )[0][5:-1]
                else:
                    site_id = getattr(entry, 'id', '')
                    pub_date = (
                        int(time.mktime(entry.published_parsed))
                        if hasattr(entry, 'published_parsed')
                        else None
                    )
                    abstract = getattr(entry, 'summary', '')
                    image = ''
            except Exception:
                site_id = getattr(entry, 'id', '')
                pub_date = None
                abstract = getattr(entry, 'summary', '')
                image = ''

            return {
                'site_id': site_id,
                'pub_date': pub_date,
                'abstract': abstract,
                'image': image,
            }

        feeds = Feed.objects.all()
        if not feeds.exists():
            self.stdout.write('No feeds found in DB. Nothing to crawl.')
            return

        existing_links = set(Article.objects.values_list('link', flat=True))

        for feed in feeds:
            self.stdout.write(f'Processing feed: {feed.name} ({feed.address})')
            parsed = feedparser.parse(feed.address)
            entries = parsed.entries
            if limit:
                entries = entries[:limit]
            added = 0
            for entry in entries:
                try:
                    if entry.link in existing_links:
                        continue
                    data = extract_entry_data(entry, feed.name)
                    # classification/vectorization (best-effort)
                    try:
                        classifier(entry.title + "\n" + data['abstract'])
                    except Exception:
                        pass
                    vec = None
                    try:
                        vec = vectorize_text(
                            entry.title + ' ' + data['abstract']
                        )
                    except Exception:
                        vec = None
                    vector_str = None
                    if vec is not None:
                        if hasattr(vec, 'tolist'):
                            vector_str = ','.join(map(str, vec.tolist()))
                        else:
                            vector_str = ','.join(map(str, vec))

                    # determine a new id: use incrementing numeric id
                    # based on existing max
                    max_id = Article.objects.all().order_by('-id').first()
                    if max_id and str(max_id.id).isdigit():
                        new_id = str(int(max_id.id) + 1)
                    else:
                        new_id = str(int(time.time()))[:10]
                    cover = get_cover(entry.link)
                    abstract = clean_caption(entry.summary)
                    article = Article(
                        id=new_id,
                        title=entry.title,
                        abstract=abstract,
                        feed=feed,
                        link=entry.link,
                        published=data['pub_date'],
                        cover=cover,
                        vector=vector_str,
                    )
                    article.save()
                    existing_links.add(entry.link)
                    added += 1
                    self.stdout.write(f'Added: {entry.title}')
                except Exception as e:
                    self.stdout.write(f'Error processing entry: {e}')
                    continue

            if added == 0:
                self.stdout.write(f'No new items for {feed.name}')
