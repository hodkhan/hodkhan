from django.core.management.base import BaseCommand
from app.models import Article


class Command(BaseCommand):
    help = 'Delete all Article rows from the database. Use --yes to confirm.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true', help='Confirm deletion',
        )

    def handle(self, *args, **options):
        if not options.get('yes'):
            self.stdout.write(
                self.style.WARNING('This will delete all Article rows.')
            )
            self.stdout.write(
                self.style.WARNING('Re-run with --yes to confirm.')
            )
            return

        count, _ = Article.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} objects.'))
