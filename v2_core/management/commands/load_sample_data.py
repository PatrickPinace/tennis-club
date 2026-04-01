"""
Management command to load sample data for testing
Usage: python manage.py load_sample_data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from v2_core.models import Facility, Court, Reservation
from datetime import datetime, timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Loads sample facilities, courts, and reservations for testing'

    def handle(self, *args, **options):
        self.stdout.write('Loading sample data...\n')

        # Create admin user if doesn't exist
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@tennis.club',
                'first_name': 'Marcin',
                'last_name': 'Kowalski',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin')
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created admin user: {admin.username}'))
        else:
            self.stdout.write(f'  Admin user already exists: {admin.username}')

        # Create test users
        users = []
        for i in range(1, 4):
            user, created = User.objects.get_or_create(
                username=f'user{i}',
                defaults={
                    'email': f'user{i}@tennis.club',
                    'first_name': f'Gracz{i}',
                    'last_name': 'Testowy',
                }
            )
            if created:
                user.set_password('test123')
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Created user: {user.username}'))
            users.append(user)

        # Create facilities
        facility1, created = Facility.objects.get_or_create(
            name='Ace Tennis Club',
            defaults={
                'address': 'ul. Sportowa 15, Warszawa',
                'description': 'Nowoczesny klub tenisowy z kortami ziemnymi i twardymi',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created facility: {facility1.name}'))

        facility2, created = Facility.objects.get_or_create(
            name='Tennis Arena Mokotów',
            defaults={
                'address': 'ul. Puławska 100, Warszawa',
                'description': 'Korty tenisowe kryte i odkryte',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created facility: {facility2.name}'))

        # Create courts for facility 1
        court_types = [
            (1, 'clay', True),
            (2, 'hard', True),
            (3, 'hard', True),
            (4, 'grass', False),
        ]

        for number, surface, indoor in court_types:
            court, created = Court.objects.get_or_create(
                facility=facility1,
                number=number,
                defaults={
                    'surface': surface,
                    'is_indoor': indoor,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created court: Kort {number}'))

        # Create courts for facility 2
        for i in range(1, 4):
            court, created = Court.objects.get_or_create(
                facility=facility2,
                number=i,
                defaults={
                    'surface': 'hard',
                    'is_indoor': i <= 2,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created court: Kort {i}'))

        # Create sample reservations for testing
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        courts = list(Court.objects.all())
        all_users = [admin] + users

        # Create reservations for today and next 7 days
        reservations_created = 0
        for day_offset in range(0, 8):
            day = today + timedelta(days=day_offset)

            # Create 2-3 reservations per day
            for hour in [10, 14, 17]:
                if day_offset == 0 and hour < now.hour:
                    continue  # Skip past hours for today

                court = courts[reservations_created % len(courts)]
                user = all_users[reservations_created % len(all_users)]

                start_time = day.replace(hour=hour, minute=0)
                end_time = start_time + timedelta(hours=1, minutes=30)

                reservation, created = Reservation.objects.get_or_create(
                    court=court,
                    start_time=start_time,
                    end_time=end_time,
                    defaults={
                        'user': user,
                        'status': 'confirmed',
                    }
                )
                if created:
                    reservations_created += 1

        self.stdout.write(self.style.SUCCESS(f'✓ Created {reservations_created} sample reservations'))

        self.stdout.write(self.style.SUCCESS('\n✅ Sample data loaded successfully!'))
        self.stdout.write('\nYou can now login with:')
        self.stdout.write('  Username: admin')
        self.stdout.write('  Password: admin')
        self.stdout.write('\nOr test users:')
        self.stdout.write('  Username: user1, user2, user3')
        self.stdout.write('  Password: test123')
