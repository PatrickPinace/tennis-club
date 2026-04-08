from rest_framework import serializers
from apps.tournaments.models import Tournament, Participant
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator
from notifications.models import Notifications
from apps.matches.models import Match
from apps.matches.tools import Results
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


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ['id', 'display_name', 'seed_number', 'status']


class TournamentSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = ['id', 'name', 'description', 'start_date', 'end_date', 'status', 'tournament_type', 'match_format', 'participants']


class TournamentListSerializer(serializers.ModelSerializer):
    """
    Lekki serializer dla listy turniejów — używany przez /api/tournaments/list/.
    Zamiast pełnej listy uczestników zwraca tylko ich liczbę.
    Dodaje: participant_count, created_by_name, facility_name.
    """
    participant_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'description',
            'start_date', 'end_date',
            'status', 'tournament_type', 'match_format',
            'rank',
            'participant_count', 'created_by_name', 'facility_name',
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_created_by_name(self, obj):
        full = obj.created_by.get_full_name()
        return full if full.strip() else obj.created_by.username

    def get_facility_name(self, obj):
        if obj.facility:
            return str(obj.facility)
        return None


class UserDetailsSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    class Meta:
        model = Notifications
        fields = ('id', 'message', 'created_at', 'is_read')


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
            raise serializers.ValidationError("Gracze w meczu muszą być unikalni.")
            
        return data

    def create(self, validated_data):
        """Set the logged-in user as p1 and create the match."""
        validated_data['p1'] = self.context['request'].user
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

    class Meta:
        model = Match
        fields = [
            'id', 'p1', 'p2', 'p3', 'p4',
            'p1_set1', 'p1_set2', 'p1_set3',
            'p2_set1', 'p2_set2', 'p2_set3',
            'match_double', 'description', 'match_date',
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


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer do rejestracji nowego użytkownika.
    """
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="Użytkownik o tym adresie e-mail już istnieje.", lookup='iexact')]
    )
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Hasła muszą być takie same."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user