from django.core.management.base import BaseCommand
from apps.rankings.services.ranking_calculator import rebuild_rankings


class Command(BaseCommand):
    help = 'Rebuild precomputed PlayerRanking snapshots from finished tournament data.'

    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['SNG', 'DBL'], help='Rebuild only this match type')
        parser.add_argument('--season', type=int, help='Rebuild only this season year')

    def handle(self, *args, **options):
        match_type = options.get('type')
        season = options.get('season')
        self.stdout.write('Rebuilding rankings...')
        count = rebuild_rankings(match_type=match_type, season=season)
        self.stdout.write(self.style.SUCCESS(f'Done. {count} player ranking records updated.'))
