# crawl_feeds.py (Continuous Crawling Version)
import uuid
import markdownify
import signal
import time
from django.core.management.base import BaseCommand

from app.management.commands.crawler_tool import get_cover, clean_caption, get_first_text_from_url, \
    fetch_and_process_html
from app.models import Feed, Article
import feedparser
import requests
import re
import os
from hazm import Normalizer, word_tokenize
import pickle
from app.management.commands.gemma_embedding import GemmaEmbedding


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Crawling cycle timed out")


class Command(BaseCommand):
    help = 'Continuously crawl feeds from the Feed model and create Article rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int,
            help='Optional max number of entries per feed to process',
        )
        parser.add_argument(
            '--device', type=str, default='auto',
            choices=['auto', 'cuda', 'cpu'],
            help='Device to use for embeddings (auto/cuda/cpu)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=32,
            help='Batch size for embedding generation',
        )
        parser.add_argument(
            '--timeout', type=int, default=300,
            help='Timeout in seconds for each crawling cycle',
        )
        parser.add_argument(
            '--sleep', type=float, default=30.0,
            help='Sleep time between cycles in seconds',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        device = options.get('device', 'auto')
        batch_size = options.get('batch_size', 32)
        timeout = options.get('timeout', 300)
        sleep_time = options.get('sleep', 1.0)

        # Load models outside the main loop
        vectorizer = None
        model = None
        try:
            with open('app/management/commands/models/hazm/vectorizer.pkl', 'rb') as f:
                vectorizer = pickle.load(f)
            with open('app/management/commands/models/hazm/logistic_regression.pkl', 'rb') as f:
                model = pickle.load(f)
        except Exception as e:
            self.stdout.write(f'Warning: classifier/vectorizer not available: {e}')

        embedding_model = None
        try:
            embedding_model = GemmaEmbedding(
                model_path='./EmbeddingGemma',
                device=device,
                batch_size=batch_size,
                normalize=True,
                cache_embeddings=True,
                seed=42
            )
            self.stdout.write(f'Loaded Gemma embedding model on device: {embedding_model.device}')
        except Exception as e:
            self.stdout.write(f'Warning: Gemma embedding model not available: {e}')

        def vectorize_text(text):
            if not embedding_model:
                return None
            return embedding_model.get_sentence_vector(text)

        def classifier(text):
            if not vectorizer or not model:
                return None
            normalizer = Normalizer()
            new_text_processed = ' '.join(word_tokenize(normalizer.normalize(text)))
            new_text_tfidf = vectorizer.transform([new_text_processed])
            return model.predict(new_text_tfidf)[0]

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

        # Set up signal handler
        signal.signal(signal.SIGALRM, timeout_handler)

        while True:
            try:
                self.stdout.write('Crawler is running...')
                signal.alarm(timeout)  # Set timeout for this cycle

                existing_links = set(Article.objects.values_list('link', flat=True))
                articles_to_embed = []
                articles_to_save = []

                feeds = Feed.objects.all()
                if not feeds.exists():
                    self.stdout.write('No feeds found in DB. Waiting for next cycle...')
                    signal.alarm(0)
                    time.sleep(sleep_time)
                    continue

                for feed in feeds:
                    try:
                        self.stdout.write(f'Processing feed: {feed.name} ({feed.address})')
                        parsed = feedparser.parse(feed.address)
                        entries = parsed.entries[:limit] if limit else parsed.entries

                        for entry in entries:
                            try:
                                if entry.link in existing_links:
                                    continue

                                data = extract_entry_data(entry, feed.name)

                                # classification (best-effort)
                                try:
                                    classifier(entry.title + "\n" + data['abstract'])
                                except Exception:
                                    pass

                                # determine a new id: use incrementing numeric id
                                # based on existing max
                                max_id = Article.objects.all().order_by('-id').first()
                                new_id = str(int(max_id.id) + 1) if max_id and str(max_id.id).isdigit() else str(int(time.time()))[:10]

                                cover = get_cover(entry.link)
                                abstract = clean_caption(entry.summary)

                                article = Article(
                                    title=entry.title,
                                    abstract=abstract,
                                    feed=feed,
                                    link=entry.link,
                                    published=data['pub_date'],
                                    cover=cover,
                                    vector=None,  # Will be set after embedding
                                )

                                articles_to_embed.append((article, entry.title + ' ' + abstract))
                                articles_to_save.append(article)

                            except Exception as e:
                                self.stdout.write(f'Error processing entry: {e}')
                                continue

                    except Exception as e:
                        self.stdout.write(f'Error processing feed {feed.name}: {e}')
                        continue

                # Process embeddings in batch
                if articles_to_embed and embedding_model:
                    self.stdout.write(f'Generating embeddings for {len(articles_to_embed)} articles...')
                    texts = [text for _, text in articles_to_embed]
                    try:
                        embeddings = embedding_model.get_embeddings(texts)
                        for (article, _), embedding in zip(articles_to_embed, embeddings):
                            if embedding is not None:
                                vector_str = ','.join(map(str, embedding.tolist() if hasattr(embedding, 'tolist') else embedding))
                                article.vector = vector_str
                    except Exception as e:
                        self.stdout.write(f'Error generating embeddings: {e}')

                # Save articles
                added = 0
                for article in articles_to_save:
                    try:
                        article.save()
                        existing_links.add(article.link)
                        added += 1
                    except Exception as e:
                        self.stdout.write(f'Error saving article: {e}')

                self.stdout.write(f'Cycle completed: Added {added} articles')

                # Clear alarm and embedding cache
                signal.alarm(0)
                if embedding_model:
                    embedding_model.clear_cache()

                self.stdout.write('End crawling cycle')
                time.sleep(sleep_time)

            except TimeoutException:
                self.stdout.write('Crawling cycle timed out, starting next cycle...')
                if embedding_model:
                    embedding_model.clear_cache()
                continue

            except Exception as e:
                self.stdout.write(f'Unexpected error in crawling cycle: {e}')
                if embedding_model:
                    embedding_model.clear_cache()
                time.sleep(sleep_time)
                continue