from datetime import date, datetime, timedelta
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status

from apps.courts.models import Reservation, TennisFacility, Court
from .serializers import MyReservationSerializer, FacilityListSerializer

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
        return (
            Reservation.objects
            .filter(user=self.request.user, status__in=['PENDING', 'CONFIRMED'])
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

    Walidacja:
      - court musi należeć do facility z reservation=True
      - end_time > start_time
      - brak kolizji z istniejącymi rezerwacjami (status != REJECTED/CHANGED)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        court_id   = request.data.get('court_id')
        date_str   = request.data.get('date')
        start_str  = request.data.get('start_time')
        end_str    = request.data.get('end_time')

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

        # Walidacja kolizji — ta sama logika co w forms.py
        conflict = Reservation.objects.filter(
            court=court,
            start_time__lt=end_dt,
            end_time__gt=start_dt,
        ).exclude(status__in=['REJECTED', 'CHANGED'])

        if conflict.exists():
            return Response({'detail': 'Ten slot jest już zajęty. Wybierz inny termin.'}, status=http_status.HTTP_409_CONFLICT)

        # Utwórz rezerwację jako PENDING (właściciel musi zatwierdzić)
        reservation = Reservation.objects.create(
            user=request.user,
            court=court,
            start_time=start_dt,
            end_time=end_dt,
            status='PENDING',
        )

        return Response({
            'id': reservation.id,
            'court_name': f'Kort {court.court_number}',
            'facility_name': court.facility.name,
            'start_time': reservation.start_time.isoformat(),
            'end_time': reservation.end_time.isoformat(),
            'status': reservation.status,
        }, status=http_status.HTTP_201_CREATED)
