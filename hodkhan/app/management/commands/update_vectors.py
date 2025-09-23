from django.core.management.base import BaseCommand
from app.models import Article
import fasttext


class Command(BaseCommand):
    help = (
        'Update Article.vector using a fasttext model for rows '
        'with null vector.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='models/fasttext/cc.fa.100.bin',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Optional max number of rows to update',
        )

    def handle(self, *args, **options):
        model_path = options.get('model')
        limit = options.get('limit')

        try:
            ft = fasttext.load_model(model_path)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to load fasttext model: {e}'
                )
            )
            return

        qs = Article.objects.filter(vector__isnull=True)
        if limit:
            qs = qs[:limit]

        updated = 0
        for a in qs:
            try:
                text = f"{a.title} {a.abstract or ''}"
                vec = ft.get_sentence_vector(text)
                if hasattr(vec, 'tolist'):
                    vec_str = ','.join(map(str, vec.tolist()))
                else:
                    vec_str = ','.join(map(str, vec))
                a.vector = vec_str
                a.save()
                updated += 1
                self.stdout.write(f'Updated vector for article {a.id}')
            except Exception as e:
                self.stdout.write(f'Error updating {a.id}: {e}')
                continue

        self.stdout.write(self.style.SUCCESS(f'Updated {updated} articles.'))
