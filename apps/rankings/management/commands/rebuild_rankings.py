from django.core.management.base import BaseCommand
from apps.rankings.services.ranking_calculator import rebuild_rankings

class Command(BaseCommand):
    help = 'Rebuilds all PlayerRanking models and updates the RankingCalculationInfo log.'

    def handle(self, *args, **options):
        self.stdout.write('Starting rebuild_rankings...')
        count = rebuild_rankings()
        self.stdout.write(self.style.SUCCESS(f'Successfully rebuilt rankings. Updated {count} records.'))
