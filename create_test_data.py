"""
Create test data for Tennis Club
Run: python manage.py shell < create_test_data.py
"""
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from v2_core.models import (
    Profile, Facility, Court, Match, Tournament,
    Participant, Reservation, Notification, TournamentConfig
)

print("Creating test data...")

# Get admin user
admin = User.objects.get(username='admin')
print(f"✓ Admin user: {admin.username}")

# Create test users (opponents)
test_users = []
users_data = [
    ('tomasz', 'Tomasz', 'Nowak', 'tomasz@tennis.club'),
    ('anna', 'Anna', 'Kowalska', 'anna@tennis.club'),
    ('jan', 'Jan', 'Wiśniewski', 'jan@tennis.club'),
    ('maria', 'Maria', 'Wójcik', 'maria@tennis.club'),
]

for username, first_name, last_name, email in users_data:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'email': email
        }
    )
    if created:
        user.set_password('test123')
        user.save()
        # Profile is auto-created by signal
        print(f"✓ Created user: {username}")
    test_users.append(user)

# Create facility and courts
facility, created = Facility.objects.get_or_create(
    name='Korty Otwock',
    defaults={
        'address': 'ul. Sportowa 1, Otwock',
        'description': 'Nowoczesne korty tenisowe w Otwocku',
        'phone': '+48 123 456 789',
        'default_surface': 'clay',
        'is_active': True,
        'owner': admin
    }
)
if created:
    print(f"✓ Created facility: {facility.name}")

# Create courts
courts = []
for i in range(1, 5):
    court, created = Court.objects.get_or_create(
        facility=facility,
        number=i,
        defaults={
            'surface': 'clay' if i <= 2 else 'hard',
            'is_indoor': i == 4,
            'is_active': True
        }
    )
    courts.append(court)
    if created:
        print(f"✓ Created court: Kort {i}")

# Create matches
now = timezone.now()
matches_data = [
    # Recent wins
    (test_users[0], 'p1', now - timedelta(days=2), [6, 6, None], [4, 3, None]),  # vs Tomasz
    (test_users[2], 'p1', now - timedelta(days=5), [7, 6, None], [5, 4, None]),  # vs Jan
    (test_users[1], 'p1', now - timedelta(days=8), [6, 6, None], [2, 1, None]),  # vs Anna

    # Recent losses
    (test_users[3], 'p2', now - timedelta(days=3), [4, 3, None], [6, 6, None]),  # vs Maria
    (test_users[0], 'p2', now - timedelta(days=7), [3, 4, None], [6, 6, None]),  # vs Tomasz
]

for opponent, winner_side, match_date, p1_scores, p2_scores in matches_data:
    match, created = Match.objects.get_or_create(
        player1=admin,
        player2=opponent,
        match_date=match_date.date(),
        defaults={
            'is_doubles': False,
            'status': 'completed',
            'winner_side': winner_side,
            'court': courts[0],
            'set1_p1': p1_scores[0], 'set1_p2': p2_scores[0],
            'set2_p1': p1_scores[1], 'set2_p2': p2_scores[1],
            'set3_p1': p1_scores[2], 'set3_p2': p2_scores[2],
            'description': 'Mecz towarzyski'
        }
    )
    if created:
        print(f"✓ Created match vs {opponent.first_name}")

# Create tournament
tournament, created = Tournament.objects.get_or_create(
    name='Puchar Jesieni',
    defaults={
        'description': 'Coroczny turniej klubowy',
        'tournament_type': 'single_elimination',
        'match_format': 'singles',
        'start_date': now + timedelta(days=3),
        'end_date': now + timedelta(days=4),
        'registration_deadline': now + timedelta(days=1),
        'status': 'registration',
        'rank': 2,
        'max_participants': 16,
        'created_by': admin,
        'facility': facility
    }
)
if created:
    print(f"✓ Created tournament: {tournament.name}")

    # Create tournament config
    TournamentConfig.objects.create(
        tournament=tournament,
        sets_to_win=2,
        games_per_set=6,
        use_seeding=True,
        third_place_match=True
    )

    # Register admin as participant
    Participant.objects.create(
        tournament=tournament,
        user=admin,
        display_name=f"{admin.first_name} {admin.last_name}",
        seed=1,
        status='registered'
    )
    print(f"✓ Registered admin in tournament")

# Create reservations
reservations_data = [
    (now + timedelta(hours=2), now + timedelta(hours=3, minutes=30), courts[2], 'confirmed'),
    (now + timedelta(days=2, hours=16), now + timedelta(days=2, hours=17, minutes=30), courts[1], 'confirmed'),
]

for start, end, court, status_val in reservations_data:
    reservation, created = Reservation.objects.get_or_create(
        user=admin,
        start_time=start,
        end_time=end,
        defaults={
            'court': court,
            'status': status_val,
            'notes': 'Rezerwacja testowa'
        }
    )
    if created:
        print(f"✓ Created reservation: {start.strftime('%d %b %H:%M')}")

# Create notifications
notifications_data = [
    ('match', 'Nowy wynik meczu', 'Twój mecz z Tomasz Nowak został zaktualizowany'),
    ('tournament', 'Zapisy na turniej', 'Zapisy na Puchar Jesieni zostały otwarte!'),
    ('reservation', 'Potwierdzona rezerwacja', 'Twoja rezerwacja kortu #3 została potwierdzona'),
]

for notif_type, title, message in notifications_data:
    notification, created = Notification.objects.get_or_create(
        user=admin,
        title=title,
        defaults={
            'notification_type': notif_type,
            'message': message,
            'is_read': False
        }
    )
    if created:
        print(f"✓ Created notification: {title}")

print("\n✅ Test data created successfully!")
print(f"   - Users: {len(test_users)} opponents")
print(f"   - Facility: {facility.name}")
print(f"   - Courts: {len(courts)}")
print(f"   - Matches: 5")
print(f"   - Tournament: {tournament.name}")
print(f"   - Reservations: 2")
print(f"   - Notifications: 3")
