from rest_framework import serializers
from apps.rankings.models import PlayerRanking

class PlayerRankingSerializer(serializers.ModelSerializer):
    """Serializer dla listy rankingowej — używany przez /api/rankings/list/"""
    display_name = serializers.SerializerMethodField()
    win_rate = serializers.SerializerMethodField()

    class Meta:
        model = PlayerRanking
        fields = [
            'position', 'display_name',
            'points', 'matches_played', 'matches_won', 'matches_lost',
            'sets_won', 'sets_lost', 'win_rate',
            'match_type', 'season',
        ]

    def get_display_name(self, obj):
        full = obj.user.get_full_name()
        return full if full.strip() else obj.user.username

    def get_win_rate(self, obj):
        if obj.matches_played and obj.matches_played > 0:
            return round(obj.matches_won / obj.matches_played * 100)
        return 0
