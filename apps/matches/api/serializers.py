from rest_framework import serializers
from django.contrib.auth.models import User
from apps.matches.models import Match
from apps.matches.tools import Results
from apps.users.api.serializers import UserDetailsSerializer

class MatchCreateSerializer(serializers.ModelSerializer):
    """Serializer to create a new friendly match."""
    p1 = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    p2 = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    p3 = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    p4 = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Match
        fields = [
            'p1', 'p2', 'p3', 'p4',
            'p1_set1', 'p2_set1', 'p1_set2', 'p2_set2', 'p1_set3', 'p2_set3',
            'match_date', 'match_double'
        ]

    def validate(self, data):
        """
        Validate match data.
        - Check for unique players.
        - Check for required players in doubles.
        """
        is_doubles = data.get('match_double', False)
        
        players = [self.context['request'].user.pk, data.get('p2').pk]
        
        if is_doubles:
            p3 = data.get('p3')
            p4 = data.get('p4')
            if not p3 or not p4:
                raise serializers.ValidationError("W meczu deblowym wszyscy czterej gracze są wymagani.")
            players.extend([p3.pk, p4.pk])

        if len(players) != len(set(players)):
            raise serializers.ValidationError("Gracze w meczu must be unique.")
            
        return data

    def create(self, validated_data):
        """Set the logged-in user as p1 and create the match."""
        validated_data['p1'] = self.context['request'].user
        validated_data['reported_by'] = self.context['request'].user
        match = Match.objects.create(**validated_data)
        return match


class MatchHistorySerializer(serializers.ModelSerializer):
    """Serializer for match history with calculated results."""
    p1 = UserDetailsSerializer(read_only=True)
    p2 = UserDetailsSerializer(read_only=True)
    p3 = UserDetailsSerializer(read_only=True)
    p4 = UserDetailsSerializer(read_only=True)
    match_date = serializers.DateField(format="%Y-%m-%d")

    # Pola obliczeniowe
    win = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    p1_win_set = serializers.SerializerMethodField()
    p2_win_set = serializers.SerializerMethodField()
    p1_win_gem = serializers.SerializerMethodField()
    p2_win_gem = serializers.SerializerMethodField()

    reported_by = UserDetailsSerializer(read_only=True)
    confirmed_by = UserDetailsSerializer(read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'p1', 'p2', 'p3', 'p4',
            'p1_set1', 'p1_set2', 'p1_set3',
            'p2_set1', 'p2_set2', 'p2_set3',
            'match_double', 'description', 'match_date',
            'score_status', 'reported_by', 'confirmed_by',
            # Pola z wynikami
            'win', 'user',
            'p1_win_set', 'p2_win_set',
            'p1_win_gem', 'p2_win_gem'
        ]

    def _get_stats(self, obj):
        """Helper to calculate stats for a match instance."""
        if not hasattr(obj, '_stats'):
            # Konwertujemy instancję modelu na słownik, aby użyć istniejącej logiki
            match_dict = Match.objects.filter(pk=obj.pk).values().first()
            results = Results(self.context['request'])
            results.matches = [match_dict]
            results.add_statistics(self.context['request'])
            obj._stats = results.matches[0] if results.matches else {}
        return obj._stats

    def get_win(self, obj):
        return self._get_stats(obj).get('win')

    def get_user(self, obj):
        return self._get_stats(obj).get('user')

    def __getattr__(self, name):
        if name.startswith('get_p') and ('_win_set' in name or '_win_gem' in name):
            return lambda obj: self._get_stats(obj).get(name.replace('get_', ''), 0)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
