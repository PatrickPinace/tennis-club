from django.db import migrations
from django.utils import timezone


def backfill_last_seen(apps, schema_editor):
    Profile = apps.get_model('users', 'Profile')
    now = timezone.now()
    Profile.objects.filter(notifications_last_seen_at__isnull=True).update(
        notifications_last_seen_at=now
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_add_notifications_last_seen_at'),
    ]

    operations = [
        migrations.RunPython(backfill_last_seen, migrations.RunPython.noop),
    ]
