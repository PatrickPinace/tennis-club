from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_add_phone_number_to_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='notifications_last_seen_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
