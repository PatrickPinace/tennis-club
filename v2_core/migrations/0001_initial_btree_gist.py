"""
Initial migration - Enable PostgreSQL btree_gist extension.

This extension is required for ExclusionConstraint with OVERLAPS operator
used in Reservation model to prevent overlapping reservations.
"""
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Enable btree_gist extension for PostgreSQL."""

    initial = True

    dependencies = []

    operations = [
        BtreeGistExtension(),
    ]
