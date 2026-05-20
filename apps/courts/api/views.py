from datetime import date, timedelta
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

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
