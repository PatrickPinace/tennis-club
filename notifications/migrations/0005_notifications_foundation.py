from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_existing_notifications(apps, schema_editor):
    """Istniejące rekordy in-app są już dostarczone — oznacz je odpowiednio."""
    Notifications = apps.get_model('notifications', 'Notifications')
    Notifications.objects.filter(
        delivery_status='pending'
    ).update(
        channel='inapp',
        event_type='generic',
        delivery_status='delivered',
        # sent_at = created_at — ustawiamy w osobnym kroku bo auto_now_add
    )
    # sent_at: ustaw równe created_at dla wszystkich istniejących
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE notifications SET sent_at = created_at WHERE sent_at IS NULL"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_add_target_url'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Nowe pola w Notifications
        migrations.AddField(
            model_name='notifications',
            name='event_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('generic', 'Ogólne'),
                    ('court.reservation.created', 'Nowa rezerwacja kortu'),
                    ('court.reservation.accepted', 'Rezerwacja zaakceptowana'),
                    ('court.reservation.rejected', 'Rezerwacja odrzucona'),
                    ('court.reservation.cancelled', 'Rezerwacja anulowana'),
                    ('tournament.created', 'Turniej utworzony'),
                    ('tournament.started', 'Turniej rozpoczęty'),
                    ('tournament.finished', 'Turniej zakończony'),
                    ('tournament.cancelled', 'Turniej anulowany'),
                    ('tournament.participant.added', 'Dodano uczestnika'),
                    ('tournament.match.score_entered', 'Wynik meczu wpisany'),
                    ('tournament.match.walkover', 'Walkover'),
                    ('tournament.ladder.challenge_sent', 'Wyzwanie wysłane'),
                    ('tournament.ladder.challenge_accepted', 'Wyzwanie zaakceptowane'),
                    ('tournament.ladder.challenge_rejected', 'Wyzwanie odrzucone'),
                ],
                default='generic',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='channel',
            field=models.CharField(
                choices=[
                    ('inapp', 'In-app'),
                    ('email', 'Email'),
                    ('sms', 'SMS'),
                ],
                default='inapp',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='delivery_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Oczekujące'),
                    ('sent', 'Wysłane'),
                    ('delivered', 'Dostarczone'),
                    ('failed', 'Błąd dostarczenia'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # 2. Data migration — backfill istniejących rekordów
        migrations.RunPython(
            backfill_existing_notifications,
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. Nowy model NotificationPreference
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('generic', 'Ogólne'),
                        ('court.reservation.created', 'Nowa rezerwacja kortu'),
                        ('court.reservation.accepted', 'Rezerwacja zaakceptowana'),
                        ('court.reservation.rejected', 'Rezerwacja odrzucona'),
                        ('court.reservation.cancelled', 'Rezerwacja anulowana'),
                        ('tournament.created', 'Turniej utworzony'),
                        ('tournament.started', 'Turniej rozpoczęty'),
                        ('tournament.finished', 'Turniej zakończony'),
                        ('tournament.cancelled', 'Turniej anulowany'),
                        ('tournament.participant.added', 'Dodano uczestnika'),
                        ('tournament.match.score_entered', 'Wynik meczu wpisany'),
                        ('tournament.match.walkover', 'Walkover'),
                        ('tournament.ladder.challenge_sent', 'Wyzwanie wysłane'),
                        ('tournament.ladder.challenge_accepted', 'Wyzwanie zaakceptowane'),
                        ('tournament.ladder.challenge_rejected', 'Wyzwanie odrzucone'),
                    ],
                    max_length=50,
                )),
                ('channel', models.CharField(
                    choices=[
                        ('inapp', 'In-app'),
                        ('email', 'Email'),
                        ('sms', 'SMS'),
                    ],
                    default='inapp',
                    max_length=20,
                )),
                ('is_enabled', models.BooleanField(default=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_preferences',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['event_type', 'channel'],
                'unique_together': {('user', 'event_type', 'channel')},
            },
        ),
    ]
