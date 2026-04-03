from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation


class Match(models.Model):
    p1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_p1", db_column="p1")
    p2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_p2", db_column="p2")
    p3 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_as_p3", db_column="p3")
    p4 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches_as_p4", db_column="p4")

    p1_set1 = models.IntegerField(default=0)
    p1_set2 = models.IntegerField(null=True, blank=True)
    p1_set3 = models.IntegerField(null=True, blank=True)

    p2_set1 = models.IntegerField(default=0)
    p2_set2 = models.IntegerField(null=True, blank=True)
    p2_set3 = models.IntegerField(null=True, blank=True)

    match_double = models.BooleanField(default=False)
    description = models.CharField(max_length=100, default="TOWARZYSKIE")
    match_date = models.DateField()
    last_updated = models.DateTimeField(auto_now=True)

    # Odwrotna relacja do modelu Activity, umożliwiająca `match.activities.all()`
    activities = GenericRelation('activities.Activity')

    class Meta:
        db_table = "matches"
        indexes = [
            models.Index(fields=["match_date"]),
            models.Index(fields=["match_double"]),
        ]

    def __str__(self):
        p3 = f", {self.p3}" if self.p3 else ""
        p4 = f", {self.p4}" if self.p4 else ""
        return f"{self.p1} vs {self.p2}{p3}{p4} on {self.match_date}"

    def get_players(self):
        """Zwraca listę wszystkich graczy w meczu."""
        players = [self.p1, self.p2]
        if self.match_double:
            if self.p3:
                players.append(self.p3)
            if self.p4:
                players.append(self.p4)
        return players
