# crawl_feeds.py (Updated version with Gemma embeddings)
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
# CHANGED: Import GemmaEmbedding instead of fasttext
from app.management.commands.gemma_embedding import GemmaEmbedding


class Command(BaseCommand):
    help = 'Crawl feeds from the Feed model and create Article rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int,
            help='Optional max number of entries per feed to process',
        )
        # NEW: Added device and batch-size arguments
        parser.add_argument(
            '--device', type=str, default='auto',
            choices=['auto', 'cuda', 'cpu'],
            help='Device to use for embeddings (auto/cuda/cpu)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=32,
            help='Batch size for embedding generation',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        device = options.get('device', 'auto')
        batch_size = options.get('batch_size', 32)

        # Load models/vectorizers if available; be tolerant if missing in dev
        vectorizer = None
        model = None
        try:
            with open('app/management/commands/models/hazm/vectorizer.pkl', 'rb') as f:
                vectorizer = pickle.load(f)
            with open('app/management/commands/models/hazm/logistic_regression.pkl', 'rb') as f:
                model = pickle.load(f)
        except Exception:
            self.stdout.write(
                'Warning: classifier/vectorizer not available; '
                'classification will be skipped'
            )

        # CHANGED: Replace fasttext with GemmaEmbedding
        embedding_model = None
        try:
            embedding_model = GemmaEmbedding(
                model_path='./EmbeddingGemma',
                device=device,
                batch_size=batch_size,
                normalize=True,  # Normalize embeddings like FastText
                cache_embeddings=True,  # Enable caching for repeated texts
                seed=42  # For reproducibility
            )
            self.stdout.write(f'Loaded Gemma embedding model on device: {embedding_model.device}')
        except Exception as e:
            self.stdout.write(
                f'Warning: Gemma embedding model not available; '
                f'embedding generation will be skipped. Error: {e}'
            )

        def vectorize_text(text):
            # CHANGED: Use GemmaEmbedding instead of fasttext
            if not embedding_model:
                return None
            # Using get_sentence_vector for FastText compatibility
            return embedding_model.get_sentence_vector(text)

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
        
        # NEW: Batch processing for embeddings
        articles_to_embed = []
        articles_to_save = []

        for feed in feeds:
            self.stdout.write(f'Processing feed: {feed.name} ({feed.address})')
            parsed = feedparser.parse(feed.address)
            entries = parsed.entries
            if limit:
                entries = entries[:limit]
            
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
                        vector=None,  # Will be set after embedding
                    )
                    
                    # Collect for batch embedding
                    articles_to_embed.append((article, entry.title + ' ' + abstract))
                    articles_to_save.append(article)
                    
                except Exception as e:
                    self.stdout.write(f'Error processing entry: {e}')
                    continue
        
        # NEW: Batch embedding generation
        if articles_to_embed and embedding_model:
            self.stdout.write(f'Generating embeddings for {len(articles_to_embed)} articles...')
            texts = [text for _, text in articles_to_embed]
            
            try:
                # Get embeddings in batch
                embeddings = embedding_model.get_embeddings(texts)
                
                # Assign embeddings to articles
                for (article, _), embedding in zip(articles_to_embed, embeddings):
                    if embedding is not None:
                        if hasattr(embedding, 'tolist'):
                            vector_str = ','.join(map(str, embedding.tolist()))
                        else:
                            vector_str = ','.join(map(str, embedding))
                        article.vector = vector_str
            except Exception as e:
                self.stdout.write(f'Error generating embeddings: {e}')
                # Fallback to individual embedding generation
                for article, text in articles_to_embed:
                    try:
                        vec = vectorize_text(text)
                        if vec is not None:
                            if hasattr(vec, 'tolist'):
                                vector_str = ','.join(map(str, vec.tolist()))
                            else:
                                vector_str = ','.join(map(str, vec))
                            article.vector = vector_str
                    except Exception:
                        pass
        
        # Save all articles
        added = 0
        for article in articles_to_save:
            try:
                article.save()
                existing_links.add(article.link)
                added += 1
                self.stdout.write(f'Added: {article.title}')
            except Exception as e:
                self.stdout.write(f'Error saving article: {e}')
        
        if added == 0:
            self.stdout.write('No new items added')
        else:
            self.stdout.write(f'Successfully added {added} articles')
            
        # NEW: Clear embedding cache to free memory
        if embedding_model:
            embedding_model.clear_cache()