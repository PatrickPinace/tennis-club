import uuid
from datetime import date, datetime, timedelta
from django.db import models
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status

from apps.courts.models import Reservation, TennisFacility, Court
from .serializers import MyReservationSerializer, FacilityListSerializer

import django.utils.timezone as tz

GRID_START = 8   # 08:00
GRID_END   = 21  # do 21:00 (ostatni slot 20:30)


class MyReservationListView(generics.ListAPIView):
    """
    GET /api/courts/reservations/

    Zwraca listę rezerwacji kortów zalogowanego użytkownika.
    Filtruje tylko statusy PENDING i CONFIRMED — aktywne rezerwacje.
    Wyniki posortowane chronologicznie (start_time ASC).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MyReservationSerializer

    def get_queryset(self):
        now = tz.now()
        return (
            Reservation.objects
            .filter(user=self.request.user)
            .filter(
                # Aktywne (przyszłe lub trwające): PENDING i CONFIRMED — pokaż jeśli end_time > now
                models.Q(status__in=['PENDING', 'CONFIRMED'], end_time__gt=now)
                # REJECTED — pokaż przez 7 dni po terminie żeby user widział feedback
                | models.Q(status='REJECTED', end_time__gt=now - timedelta(days=7))
            )
            .select_related('court__facility')
            .order_by('start_time')
        )


class FacilityListView(generics.ListAPIView):
    """
    GET /api/courts/facilities/

    Zwraca listę obiektów z włączoną rezerwacją online.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FacilityListSerializer

    def get_queryset(self):
        return TennisFacility.objects.filter(reservation=True).order_by('name')


class TimelineView(APIView):
    """
    GET /api/courts/timeline/<facility_pk>/?date=YYYY-MM-DD

    Zwraca dane do grafiku kortów dla danego obiektu i daty.
    Format: {
      facility_name: str,
      date: str,
      courts: [{ id, name, slots: [{ time, status, is_mine }] }]
    }
    Sloty co 30 min od GRID_START:00 do GRID_END:00.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, facility_pk):
        facility = TennisFacility.objects.filter(pk=facility_pk, reservation=True).first()
        if not facility:
            return Response({'detail': 'Obiekt nie istnieje.'}, status=404)

        date_str = request.GET.get('date', date.today().isoformat())
        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            selected_date = date.today()

        courts = Court.objects.filter(facility=facility).order_by('court_number')

        # Mapa slot_time → dane rezerwacji dla każdego kortu
        courts_data = []
        for court in courts:
            reservations = (
                Reservation.objects
                .filter(
                    court=court,
                    start_time__date=selected_date,
                )
                .exclude(status__in=['REJECTED', 'CHANGED'])
                .select_related('user')
            )

            # Buduj mapę slotów: HH:MM → {status, is_mine}
            slot_map: dict = {}
            for res in reservations:
                cur = res.start_time
                while cur < res.end_time:
                    h, m = cur.hour, cur.minute
                    if GRID_START <= h < GRID_END:
                        key = f'{h:02d}:{m:02d}'
                        slot_map[key] = {
                            'status': res.status,
                            'is_mine': res.user_id == request.user.pk,
                        }
                    cur += timedelta(minutes=30)

            # Generuj pełną listę slotów w zakresie gridu
            slots = []
            h = GRID_START
            m = 0
            while h < GRID_END:
                key = f'{h:02d}:{m:02d}'
                info = slot_map.get(key)
                slots.append({
                    'time': key,
                    'status': info['status'] if info else 'FREE',
                    'is_mine': info['is_mine'] if info else False,
                })
                m += 30
                if m == 60:
                    m = 0
                    h += 1

            courts_data.append({
                'id': court.id,
                'name': f'Kort {court.court_number}',
                'slots': slots,
            })

        return Response({
            'facility_name': facility.name,
            'date': selected_date.isoformat(),
            'courts': courts_data,
        })


class CreateReservationView(APIView):
    """
    POST /api/courts/reserve/

    Tworzy rezerwację kortu dla zalogowanego użytkownika.
    Status domyślnie PENDING (właściciel musi zatwierdzić).

    Body (JSON):
      court_id   — int, wymagane
      date       — str, 'YYYY-MM-DD', wymagane
      start_time — str, 'HH:MM', wymagane
      end_time   — str, 'HH:MM', wymagane
      recurring  — bool, opcjonalne (domyślnie false)
      weeks      — int 2–12, wymagane jeśli recurring=true

    Walidacja:
      - court musi należeć do facility z reservation=True
      - end_time > start_time
      - brak kolizji z istniejącymi rezerwacjami (status != REJECTED/CHANGED)
      - dla serii: atomowa — jeśli którekolwiek wystąpienie ma konflikt, cała seria jest odrzucana
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        court_id   = request.data.get('court_id')
        date_str   = request.data.get('date')
        start_str  = request.data.get('start_time')
        end_str    = request.data.get('end_time')
        recurring  = request.data.get('recurring', False)
        weeks_raw  = request.data.get('weeks')

        # Walidacja wymaganych pól
        missing = [f for f, v in [('court_id', court_id), ('date', date_str), ('start_time', start_str), ('end_time', end_str)] if not v]
        if missing:
            return Response({'detail': f'Brakujące pola: {", ".join(missing)}.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # Pobierz kort i sprawdź czy facility ma rezerwację online
        try:
            court = Court.objects.select_related('facility').get(pk=court_id)
        except Court.DoesNotExist:
            return Response({'detail': 'Kort nie istnieje.'}, status=http_status.HTTP_404_NOT_FOUND)

        if not court.facility.reservation:
            return Response({'detail': 'Ten obiekt nie przyjmuje rezerwacji online.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # Parsowanie dat
        try:
            res_date   = date.fromisoformat(date_str)
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time   = datetime.strptime(end_str,   '%H:%M').time()
        except ValueError:
            return Response({'detail': 'Nieprawidłowy format daty lub czasu (oczekiwany YYYY-MM-DD, HH:MM).'}, status=http_status.HTTP_400_BAD_REQUEST)

        start_dt = datetime.combine(res_date, start_time)
        end_dt   = datetime.combine(res_date, end_time)

        # end > start
        if start_dt >= end_dt:
            return Response({'detail': 'Godzina zakończenia musi być późniejsza niż rozpoczęcia.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # Sloty muszą być wyrównane do siatki 30 min
        if start_time.minute % 30 != 0 or end_time.minute % 30 != 0:
            return Response({'detail': 'Godziny rezerwacji muszą być wyrównane do pełnej lub połówki godziny (np. 09:00, 09:30).'}, status=http_status.HTTP_400_BAD_REQUEST)

        # Sloty muszą mieścić się w dozwolonym zakresie godzin (GRID_START–GRID_END)
        if start_time.hour < GRID_START or end_time.hour > GRID_END or (end_time.hour == GRID_END and end_time.minute > 0):
            return Response(
                {'detail': f'Rezerwacje są możliwe tylko w godzinach {GRID_START:02d}:00–{GRID_END:02d}:00.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Nie można tworzyć rezerwacji w przeszłości ani dla slotów które już minęły
        now = tz.now()
        if start_dt <= now:
            return Response({'detail': 'Nie można zarezerwować kortu na termin, który już minął lub właśnie trwa.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # ── Pojedyncza rezerwacja ──────────────────────────────────────────
        if not recurring:
            conflict = Reservation.objects.filter(
                court=court,
                start_time__lt=end_dt,
                end_time__gt=start_dt,
            ).exclude(status__in=['REJECTED', 'CHANGED'])
            if conflict.exists():
                return Response({'detail': 'Ten slot jest już zajęty. Wybierz inny termin.'}, status=http_status.HTTP_409_CONFLICT)

            reservation = Reservation.objects.create(
                user=request.user,
                court=court,
                start_time=start_dt,
                end_time=end_dt,
                status='PENDING',
            )

            # Powiadom ownera o nowej rezerwacji (nie notyfikuj gdy user == owner)
            _owner = court.facility.owner
            if _owner and _owner.pk != request.user.pk:
                from notifications.helpers import notify
                _date_str = start_dt.strftime('%d.%m.%Y %H:%M')
                _court_label = f'kort nr {court.court_number}'
                _user_name = request.user.get_full_name() or request.user.username
                notify(
                    _owner,
                    f'🎾 Nowa rezerwacja od {_user_name} ({_court_label}, {_date_str}) oczekuje na Twoją akceptację.',
                )

            return Response({
                'id': reservation.id,
                'court_name': f'Kort {court.court_number}',
                'facility_name': court.facility.name,
                'start_time': reservation.start_time.isoformat(),
                'end_time': reservation.end_time.isoformat(),
                'status': reservation.status,
                'series_id': None,
            }, status=http_status.HTTP_201_CREATED)

        # ── Rezerwacja cykliczna (co tydzień) ─────────────────────────────
        try:
            weeks = int(weeks_raw)
        except (TypeError, ValueError):
            weeks = 0
        if not (2 <= weeks <= 12):
            return Response(
                {'detail': 'Dla rezerwacji cyklicznej weeks musi być liczbą od 2 do 12.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Generuj listę (start_dt, end_dt) dla każdego tygodnia
        occurrences = [
            (start_dt + timedelta(weeks=i), end_dt + timedelta(weeks=i))
            for i in range(weeks)
        ]

        # Atomowe sprawdzenie konfliktów — wszystkie wystąpienia
        conflict_dates = []
        for s, e in occurrences:
            if Reservation.objects.filter(
                court=court,
                start_time__lt=e,
                end_time__gt=s,
            ).exclude(status__in=['REJECTED', 'CHANGED']).exists():
                conflict_dates.append(s.strftime('%d.%m.%Y'))

        if conflict_dates:
            dates_str = ', '.join(conflict_dates)
            return Response(
                {'detail': f'Seria nie może być utworzona — konflikty w terminach: {dates_str}. Wybierz inny slot lub zmniejsz liczbę tygodni.'},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Utwórz wszystkie rezerwacje serii atomowo
        series_uuid = uuid.uuid4()
        reservations = Reservation.objects.bulk_create([
            Reservation(
                user=request.user,
                court=court,
                start_time=s,
                end_time=e,
                status='PENDING',
                series_id=series_uuid,
            )
            for s, e in occurrences
        ])

        # Powiadom ownera — jedna zbiorcza notyfikacja dla całej serii
        _owner = court.facility.owner
        if _owner and _owner.pk != request.user.pk:
            from notifications.helpers import notify
            _first_str = occurrences[0][0].strftime('%d.%m.%Y %H:%M')
            _court_label = f'kort nr {court.court_number}'
            _user_name = request.user.get_full_name() or request.user.username
            notify(
                _owner,
                f'🎾 Nowa seria {len(reservations)} rezerwacji od {_user_name} ({_court_label}, pierwsza: {_first_str}) oczekuje na akceptację.',
            )

        return Response({
            'series_id': str(series_uuid),
            'count': len(reservations),
            'court_name': f'Kort {court.court_number}',
            'facility_name': court.facility.name,
            'first_start': occurrences[0][0].isoformat(),
            'last_start': occurrences[-1][0].isoformat(),
            'status': 'PENDING',
        }, status=http_status.HTTP_201_CREATED)


class CancelReservationView(APIView):
    """
    DELETE /api/courts/reservations/<id>/

    Anuluje (usuwa) własną rezerwację zalogowanego użytkownika.

    Reguły:
      - Użytkownik może anulować tylko swoją rezerwację.
      - Dozwolone statusy: PENDING, CONFIRMED.
      - Nie można anulować rezerwacji z przeszłości (start_time < teraz).
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            reservation = Reservation.objects.select_related('court__facility').get(pk=pk)
        except Reservation.DoesNotExist:
            return Response({'detail': 'Rezerwacja nie istnieje.'}, status=http_status.HTTP_404_NOT_FOUND)

        # Tylko właściciel rezerwacji
        if reservation.user_id != request.user.pk:
            return Response({'detail': 'Brak uprawnień.'}, status=http_status.HTTP_403_FORBIDDEN)

        # Tylko aktywne statusy
        if reservation.status not in ('PENDING', 'CONFIRMED'):
            return Response(
                {'detail': 'Nie można anulować rezerwacji o tym statusie.'},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Nie można anulować przeszłych rezerwacji
        now = tz.now()
        if reservation.start_time <= now:
            return Response(
                {'detail': 'Nie można anulować rezerwacji, która już się rozpoczęła lub minęła.'},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Pobierz dane do notyfikacji przed usunięciem
        _owner = reservation.court.facility.owner if reservation.court else None
        _date_str = reservation.start_time.strftime('%d.%m.%Y %H:%M')
        _court_label = f'kort nr {reservation.court.court_number}' if reservation.court else 'kort'
        _user_name = request.user.get_full_name() or request.user.username

        reservation.delete()

        # Powiadom ownera o anulowaniu (guard: owner istnieje i nie jest samym anulującym)
        if _owner and _owner.pk != request.user.pk:
            from notifications.helpers import notify
            notify(
                _owner,
                f'❌ {_user_name} anulował rezerwację ({_court_label}, {_date_str}).',
            )

        return Response(status=http_status.HTTP_204_NO_CONTENT)


class PendingReservationsView(generics.ListAPIView):
    """
    GET /api/courts/reservations/pending/

    Zwraca oczekujące rezerwacje (PENDING) dla obiektów, których właścicielem
    jest zalogowany użytkownik, lub wszystkie PENDING jeśli is_staff.
    Posortowane chronologicznie.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MyReservationSerializer

    def get_queryset(self):
        user = self.request.user
        now  = tz.now()
        qs = (
            Reservation.objects
            .filter(status='PENDING', end_time__gt=now)
            .select_related('court__facility', 'user')
            .order_by('start_time')
        )
        if user.is_staff:
            return qs
        return qs.filter(court__facility__owner=user)

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        # Rozszerzamy serializer o dane usera składającego rezerwację
        data = []
        for r in qs:
            data.append({
                'id': r.id,
                'court_name': f'Kort {r.court.court_number}' if r.court else None,
                'facility_name': r.court.facility.name if r.court else None,
                'start_time': r.start_time.isoformat(),
                'end_time': r.end_time.isoformat(),
                'status': r.status,
                'user_name': r.user.get_full_name() or r.user.username,
            })
        return Response(data)


class ReservationStatusView(APIView):
    """
    PATCH /api/courts/reservations/<id>/status/

    Zmienia status rezerwacji przez właściciela obiektu lub is_staff.

    Body (JSON):
      action — 'approve' | 'reject'

    Reguły:
      - Tylko właściciel facility (facility.owner) lub is_staff.
      - approve: PENDING → CONFIRMED
      - reject:  PENDING → REJECTED
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            reservation = (
                Reservation.objects
                .select_related('court__facility', 'user')
                .get(pk=pk)
            )
        except Reservation.DoesNotExist:
            return Response({'detail': 'Rezerwacja nie istnieje.'}, status=http_status.HTTP_404_NOT_FOUND)

        # Uprawnienia: właściciel facility lub is_staff
        is_owner = (
            reservation.court and
            reservation.court.facility.owner_id == request.user.pk
        )
        if not (is_owner or request.user.is_staff):
            return Response({'detail': 'Brak uprawnień.'}, status=http_status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ('approve', 'reject'):
            return Response(
                {'detail': 'Nieprawidłowa akcja. Dozwolone: approve, reject.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if reservation.status != 'PENDING':
            return Response(
                {'detail': f'Rezerwacja nie jest w statusie PENDING (aktualny: {reservation.status}).'},
                status=http_status.HTTP_409_CONFLICT,
            )

        new_status = 'CONFIRMED' if action == 'approve' else 'REJECTED'
        reservation.status = new_status
        reservation.save(update_fields=['status'])

        # Powiadom rezerwującego (nie notyfikuj samego siebie jeśli owner rezerwuje własny kort)
        if reservation.user and reservation.user.pk != request.user.pk:
            from notifications.helpers import notify
            _date_str = reservation.start_time.strftime('%d.%m.%Y %H:%M') if reservation.start_time else '?'
            _court_label = (
                f'kort nr {reservation.court.court_number}' if reservation.court else 'kort'
            )
            if action == 'approve':
                notify(
                    reservation.user,
                    f'✅ Twoja rezerwacja ({_court_label}, {_date_str}) została potwierdzona.',
                )
            else:
                notify(
                    reservation.user,
                    f'❌ Twoja rezerwacja ({_court_label}, {_date_str}) została odrzucona.',
                )

        return Response({
            'id': reservation.id,
            'status': reservation.status,
        })


class CancelSeriesView(APIView):
    """
    DELETE /api/courts/series/<series_uuid>/

    Anuluje wszystkie przyszłe rezerwacje należące do serii (tego usera).

    Reguły:
      - Tylko właściciel serii (user) może anulować.
      - Usuwa tylko przyszłe wystąpienia (start_time > teraz).
      - Statusy PENDING i CONFIRMED są anulowane; REJECTED pomijane.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, series_uuid):
        try:
            series_id = uuid.UUID(str(series_uuid))
        except ValueError:
            return Response({'detail': 'Nieprawidłowy identyfikator serii.'}, status=http_status.HTTP_400_BAD_REQUEST)

        now = tz.now()
        deleted_qs = Reservation.objects.filter(
            series_id=series_id,
            user=request.user,
            start_time__gt=now,
            status__in=['PENDING', 'CONFIRMED'],
        )

        if not deleted_qs.exists():
            return Response(
                {'detail': 'Brak przyszłych rezerwacji tej serii do anulowania.'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Pobierz dane do notyfikacji przed usunięciem (po delete queryset pusty)
        _first = deleted_qs.select_related('court__facility').order_by('start_time').first()
        _owner = _first.court.facility.owner if (_first and _first.court) else None
        _court_label = f'kort nr {_first.court.court_number}' if (_first and _first.court) else 'kort'
        _first_str = _first.start_time.strftime('%d.%m.%Y %H:%M') if _first else '?'
        _user_name = request.user.get_full_name() or request.user.username

        count, _ = deleted_qs.delete()

        # Jedna zbiorcza notyfikacja do ownera (guard: owner istnieje i nie jest anulującym)
        if _owner and _owner.pk != request.user.pk:
            from notifications.helpers import notify
            notify(
                _owner,
                f'❌ {_user_name} anulował serię {count} rezerwacji ({_court_label}, pierwsza: {_first_str}).',
            )

        return Response({'cancelled': count}, status=http_status.HTTP_200_OK)
