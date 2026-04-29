from rest_framework import serializers
from apps.tournaments.models import Tournament, Participant, TournamentsMatch, RoundRobinConfig
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
    user_id = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)

    class Meta:
        model = Participant
        fields = ['id', 'display_name', 'seed_number', 'status', 'user_id']


class TournamentSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = ['id', 'name', 'description', 'start_date', 'end_date', 'status', 'tournament_type', 'match_format', 'participants']

    def get_participants(self, obj):
        qs = obj.participants.exclude(status='WDN')
        return ParticipantSerializer(qs, many=True).data


class TournamentListSerializer(serializers.ModelSerializer):
    """
    Lekki serializer dla listy turniejów — używany przez /api/tournaments/list/.
    Zamiast pełnej listy uczestników zwraca tylko ich liczbę.
    Dodaje: participant_count, created_by_name, facility_name, matches_progress.
    """
    participant_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()
    matches_progress = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'description',
            'start_date', 'end_date',
            'status', 'tournament_type', 'match_format',
            'rank',
            'participant_count', 'created_by_name', 'facility_name',
            'matches_progress',
        ]

    def get_participant_count(self, obj):
        return obj.participants.exclude(status='WDN').count()

    def get_created_by_name(self, obj):
        full = obj.created_by.get_full_name()
        return full if full.strip() else obj.created_by.username

    def get_facility_name(self, obj):
        if obj.facility:
            return str(obj.facility)
        return None

    def get_matches_progress(self, obj):
        """Postęp meczów — done/total (bez CNC). Tylko dla ACT/FIN."""
        if obj.status not in ('ACT', 'FIN'):
            return None
        all_matches = obj.matches.exclude(status='CNC')
        total = all_matches.count()
        if total == 0:
            return None
        done = all_matches.filter(status__in=['CMP', 'WDR']).count()
        return {'done': done, 'total': total}


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

# ── Tournament Detail (Round Robin) ──────────────────────────────────────────

class TournamentMatchSerializer(serializers.ModelSerializer):
    """Mecz turniejowy — dla listy meczów w detalu turnieju."""
    participant1_name = serializers.SerializerMethodField()
    participant2_name = serializers.SerializerMethodField()
    winner_name = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()

    class Meta:
        model = TournamentsMatch
        fields = [
            'id', 'round_number', 'match_index', 'status',
            'participant1_id', 'participant2_id',
            'participant1_name', 'participant2_name', 'winner_name',
            'set1_p1_score', 'set1_p2_score',
            'set2_p1_score', 'set2_p2_score',
            'set3_p1_score', 'set3_p2_score',
            'score', 'scheduled_time',
        ]

    def get_participant1_name(self, obj):
        return obj.participant1.display_name if obj.participant1 else None

    def get_participant2_name(self, obj):
        return obj.participant2.display_name if obj.participant2 else None

    def get_winner_name(self, obj):
        return obj.winner.display_name if obj.winner else None

    def get_score(self, obj):
        """Zwraca wynik jako string, np. '6:3 6:4' lub None gdy mecz nie zakończony."""
        parts = []
        for i in range(1, 4):
            s1 = getattr(obj, f'set{i}_p1_score', None)
            s2 = getattr(obj, f'set{i}_p2_score', None)
            if s1 is not None and s2 is not None:
                parts.append(f'{s1}:{s2}')
        return ' '.join(parts) if parts else None


class RoundRobinConfigSerializer(serializers.ModelSerializer):
    """Konfiguracja punktacji dla Round Robin — odczyt (GET detail)."""
    class Meta:
        model = RoundRobinConfig
        fields = [
            'max_participants', 'sets_to_win', 'games_per_set',
            'points_for_win', 'points_for_loss',
            'points_for_set_win', 'points_for_set_loss',
            'points_for_gem_win', 'points_for_gem_loss',
            'points_for_supertiebreak_win', 'points_for_supertiebreak_loss',
            'tie_breaker_priority',
        ]


class RoundRobinConfigUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer do PATCH /api/tournaments/{id}/config/

    Wszystkie pola opcjonalne (partial update).
    Walidacja:
    - sets_to_win i games_per_set zablokowane gdy turniej ACT/FIN/CNC/SCH
    - points_for_win >= points_for_loss (logika: winner powinien dostawać ≥ przegrany)
    - min_participants >= 2, sets_to_win >= 1, games_per_set >= 1
    - punkty z zakresu [-100, 100]
    """
    class Meta:
        model = RoundRobinConfig
        fields = [
            'max_participants', 'sets_to_win', 'games_per_set',
            'points_for_win', 'points_for_loss',
            'points_for_set_win', 'points_for_set_loss',
            'points_for_gem_win', 'points_for_gem_loss',
            'points_for_supertiebreak_win', 'points_for_supertiebreak_loss',
            'tie_breaker_priority',
        ]

    def validate(self, attrs):
        tournament = self.instance.tournament
        locked_statuses = {'ACT', 'FIN', 'CNC', 'SCH'}

        # Pola strukturalne zablokowane po starcie turnieju
        if tournament.status in locked_statuses:
            for field in ('sets_to_win', 'games_per_set'):
                if field in attrs:
                    raise serializers.ValidationError({
                        field: f'Nie można zmieniać „{field}" po rozpoczęciu turnieju (status: {tournament.status}).'
                    })

        # Limity dla pól liczbowych
        if 'max_participants' in attrs and attrs['max_participants'] < 2:
            raise serializers.ValidationError({'max_participants': 'Minimalna liczba uczestników to 2.'})
        if 'sets_to_win' in attrs and attrs['sets_to_win'] < 1:
            raise serializers.ValidationError({'sets_to_win': 'sets_to_win musi wynosić co najmniej 1.'})
        if 'games_per_set' in attrs and attrs['games_per_set'] < 1:
            raise serializers.ValidationError({'games_per_set': 'games_per_set musi wynosić co najmniej 1.'})

        # Zakres punktów [-100, 100]
        point_fields = [
            'points_for_win', 'points_for_loss',
            'points_for_set_win', 'points_for_set_loss',
            'points_for_gem_win', 'points_for_gem_loss',
            'points_for_supertiebreak_win', 'points_for_supertiebreak_loss',
        ]
        for f in point_fields:
            if f in attrs and not (-100 <= float(attrs[f]) <= 100):
                raise serializers.ValidationError({f: f'Wartość musi być z zakresu [-100, 100].'})

        return attrs


class RoundRobinStandingSerializer(serializers.Serializer):
    """
    Serializer dla jednego wiersza tabeli Round Robin.
    Używany przez GET /api/tournaments/{id}/standings/

    Dane obliczane przez calculate_round_robin_standings() w tools.py,
    wzbogacone o draws, win_rate i position w widoku RoundRobinStandingsView.
    """
    position        = serializers.IntegerField()
    participant_id  = serializers.IntegerField()
    display_name    = serializers.CharField()
    matches_played  = serializers.IntegerField()
    wins            = serializers.IntegerField()
    losses          = serializers.IntegerField()
    draws           = serializers.IntegerField()
    sets_won        = serializers.IntegerField()
    sets_lost       = serializers.IntegerField()
    sets_diff       = serializers.IntegerField()
    games_won       = serializers.IntegerField()
    games_lost      = serializers.IntegerField()
    games_diff      = serializers.IntegerField()
    points          = serializers.DecimalField(max_digits=10, decimal_places=2)
    win_rate        = serializers.FloatField(
        help_text='Procent wygranych meczów (0–100). null gdy brak rozegranych meczów.'
    )


class TournamentDetailSerializer(serializers.ModelSerializer):
    """
    Pełny serializer detalu turnieju dla frontendu Astro.
    Używany przez GET /api/tournaments/{id}/detail/
    Dla Round Robin: zawiera config, mecze, tabelę standings.
    Dla innych typów: tylko podstawowe dane + uczestnicy.
    """
    participants = serializers.SerializerMethodField()
    matches = serializers.SerializerMethodField()
    standings = serializers.SerializerMethodField()
    config = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    matches_progress = serializers.SerializerMethodField()

    def get_participants(self, obj):
        qs = obj.participants.exclude(status='WDN')
        return ParticipantSerializer(qs, many=True).data

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'description',
            'start_date', 'end_date',
            'status', 'tournament_type', 'match_format', 'rank',
            'facility_name', 'created_by_name', 'created_by_username',
            'participant_count', 'participants',
            'config', 'matches', 'standings',
            'matches_progress',
        ]

    def get_facility_name(self, obj):
        return str(obj.facility) if obj.facility else None

    def get_created_by_name(self, obj):
        full = obj.created_by.get_full_name()
        return full if full.strip() else obj.created_by.username

    def get_created_by_username(self, obj):
        return obj.created_by.username

    def get_participant_count(self, obj):
        return obj.participants.exclude(status='WDN').count()

    def get_config(self, obj):
        if obj.tournament_type == 'RND':
            cfg = getattr(obj, 'round_robin_config', None)
            if cfg:
                return RoundRobinConfigSerializer(cfg).data
        if obj.tournament_type == 'AMR':
            cfg = getattr(obj, 'americano_config', None)
            if cfg:
                return {
                    'points_per_match': cfg.points_per_match,
                    'number_of_rounds': cfg.number_of_rounds,
                    'scheduling_type': cfg.scheduling_type,
                }
        return None

    def get_matches(self, obj):
        matches = (
            obj.matches
            .select_related('participant1', 'participant2', 'winner')
            .order_by('round_number', 'match_index')
        )
        return TournamentMatchSerializer(matches, many=True).data

    def get_standings(self, obj):
        """Oblicza tabelę standings — RR lub Americano."""
        if obj.tournament_type == 'RND':
            try:
                from apps.tournaments.tools import calculate_round_robin_standings
                from apps.tournaments.models import RoundRobinConfig
                participants = obj.participants.filter(status__in=['ACT', 'REG'])
                config = getattr(obj, 'round_robin_config', None)
                if config is None:
                    config, _ = RoundRobinConfig.objects.get_or_create(tournament=obj)
                standings = calculate_round_robin_standings(obj, participants, config)
                return [
                    {
                        'participant_id': s['participant'].id,
                        'display_name': s['participant'].display_name,
                        'points': float(s['points']),
                        'matches_played': s['matches_played'],
                        'wins': s['wins'],
                        'losses': s['losses'],
                        'sets_won': s['sets_won'],
                        'sets_lost': s['sets_lost'],
                        'games_won': s['games_won'],
                        'games_lost': s['games_lost'],
                        'sets_diff': s['sets_diff'],
                        'games_diff': s['games_diff'],
                    }
                    for s in standings
                ]
            except Exception:
                return None

        if obj.tournament_type == 'AMR':
            try:
                from apps.tournaments.tools import calculate_americano_standings
                standings = calculate_americano_standings(obj)
                return [
                    {
                        'participant_id': s['participant'].id,
                        'display_name': s['participant'].display_name,
                        'points': s['points'],
                        'matches_played': s['matches_played'],
                    }
                    for s in standings
                ]
            except Exception:
                return None

        return None

    def get_matches_progress(self, obj):
        """
        Zwraca postęp meczów: { done, total }.
        done  = CMP + WDR (rozegrane lub walkower)
        total = wszystkie mecze bez CNC (anulowane nie liczą się do puli)
        """
        from django.db.models import Q
        all_matches = obj.matches.exclude(status='CNC')
        total = all_matches.count()
        done = all_matches.filter(status__in=['CMP', 'WDR']).count()
        return {'done': done, 'total': total}
