# friends/migrations/0003_rename_onlinefriend_friend_remove_offlinefriend_user_and_more.py

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('friends', '0002_alter_offlinefriend_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # PRZYWRÓCONO: Ta operacja definiuje model 'Friend' w stanie migracji,
        # zapobiegając błędowi KeyError.
        migrations.RenameModel(
            old_name='OnlineFriend',
            new_name='Friend',
        ),
        
        # USUNIĘTO/ZAKOMENTOWANO: Operacja RemoveField i RunSQL
        # Powodowały błąd (1091: Can't DROP COLUMN `user_id`; check that it exists).
        # Zakładamy, że kolumna/indeks zostały już usunięte w bazie danych.
        # migrations.RemoveField(
        #     model_name='offlinefriend',
        #     name='user',
        # ),
        # migrations.RunSQL(
        #     sql='ALTER TABLE `friends_onlinefriend` DROP INDEX `unique_online_friend`',
        #     reverse_sql=migrations.RunSQL.noop,
        # ),

        # POZOSTAŁE OPERACJE (model 'Friend' jest już zdefiniowany w stanie migracji)
        
        # Dodanie nowego ograniczenia do modelu 'Friend'
        migrations.AddConstraint(
            model_name='friend',
            constraint=models.UniqueConstraint(fields=('user', 'friend'), name='unique_friend'),
        ),
        
        # Zmiana nazwy tabeli w bazie danych (teraz działa na modelu 'Friend')
        migrations.AlterModelTable(
            name='friend',
            table='user_friend',
        ),
        
        # Usunięcie zbędnego modelu
        migrations.DeleteModel(
            name='OfflineFriend',
        ),
    ]