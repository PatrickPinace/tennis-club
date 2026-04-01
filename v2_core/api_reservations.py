"""
REST API views for Reservations (Sprint 3)
Endpoints for facilities, courts, reservations availability and CRUD
"""
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from datetime import datetime, timedelta, time
from django.utils import timezone

from .models import (
    Facility, Court, Reservation
)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def facilities_list(request):
    """
    Get all active facilities
    GET /api/facilities/
    """
    facilities = Facility.objects.filter(is_active=True).order_by('name')

    data = [
        {
            'id': f.id,
            'name': f.name,
            'city': f.address.split(',')[-1].strip() if f.address else None
        }
        for f in facilities
    ]

    return Response(data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def courts_list(request):
    """
    Get courts for a facility
    GET /api/courts/?facility_id=1
    GET /api/courts/ (all courts)
    """
    facility_id = request.query_params.get('facility_id')

    if facility_id:
        courts = Court.objects.filter(
            facility_id=facility_id,
            is_active=True
        ).order_by('number')
    else:
        # Return all courts from all facilities
        courts = Court.objects.filter(
            is_active=True
        ).order_by('facility__name', 'number')

    data = [
        {
            'id': c.id,
            'number': c.number,
            'surface': c.get_surface_display(),
            'is_active': c.is_active,
            'facility': {
                'id': c.facility.id,
                'name': c.facility.name
            }
        }
        for c in courts
    ]

    return Response(data)


def generate_time_slots(date, start_hour=6, end_hour=23, slot_minutes=30):
    """
    Generate time slots for a given date
    Returns list of (start_datetime, end_datetime) tuples
    """
    slots = []
    current_time = datetime.combine(date, time(start_hour, 0))
    end_time = datetime.combine(date, time(end_hour, 0))

    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=slot_minutes)
        slots.append((current_time, slot_end))
        current_time = slot_end

    return slots


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def reservations_availability(request):
    """
    Get availability for a specific date and facility
    GET /api/reservations/availability/?date=2026-03-29&facility_id=1

    Returns:
    - date
    - facility info
    - courts list
    - slots (available, booked, blocked)
    """
    date_str = request.query_params.get('date')
    facility_id = request.query_params.get('facility_id')

    if not date_str or not facility_id:
        return Response(
            {'error': 'date and facility_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get facility
    try:
        facility = Facility.objects.get(id=facility_id, is_active=True)
    except Facility.DoesNotExist:
        return Response(
            {'error': 'Facility not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get courts
    courts = Court.objects.filter(facility=facility, is_active=True).order_by('number')

    if not courts.exists():
        return Response({
            'date': date_str,
            'facility': {
                'id': facility.id,
                'name': facility.name,
                'city': facility.address.split(',')[-1].strip() if facility.address else None
            },
            'courts': [],
            'slots': []
        })

    # Get all reservations for this date and facility
    reservations = Reservation.objects.filter(
        court__facility=facility,
        start_time__date=target_date,
        status__in=['pending', 'confirmed']
    ).select_related('court', 'user')

    # Build slots
    slots = []
    for reservation in reservations:
        slots.append({
            'court_id': reservation.court.id,
            'court_name': f"Kort {reservation.court.number}",
            'start': reservation.start_time.isoformat(),
            'end': reservation.end_time.isoformat(),
            'status': 'booked',
            'reservation_id': reservation.id,
            'reserved_by_me': reservation.user == request.user
        })

    courts_data = [
        {
            'id': c.id,
            'facility_id': c.facility_id,
            'name': f"Kort {c.number}",
            'surface': c.get_surface_display(),
            'is_active': c.is_active
        }
        for c in courts
    ]

    return Response({
        'date': date_str,
        'facility': {
            'id': facility.id,
            'name': facility.name,
            'city': facility.address.split(',')[-1].strip() if facility.address else None
        },
        'courts': courts_data,
        'slots': slots
    })


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def my_reservations(request):
    """
    Get user's reservations from a specific date
    GET /api/reservations/my/?from=2026-03-29
    """
    from_date_str = request.query_params.get('from')

    if not from_date_str:
        from_date = timezone.now().date()
    else:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

    reservations = Reservation.objects.filter(
        user=request.user,
        start_time__date__gte=from_date,
        status__in=['pending', 'confirmed']
    ).select_related('court', 'court__facility').order_by('start_time')

    data = [
        {
            'id': r.id,
            'court_id': r.court.id,
            'court_name': f"Kort {r.court.number}",
            'facility_id': r.court.facility.id,
            'facility_name': r.court.facility.name,
            'start': r.start_time.isoformat(),
            'end': r.end_time.isoformat(),
            'status': r.status,
            'reserved_by_me': True
        }
        for r in reservations
    ]

    return Response(data)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_reservation(request):
    """
    Create a new reservation
    POST /api/reservations/

    Body:
    {
        "court_id": 3,
        "start": "2026-03-29T09:30:00+02:00",
        "end": "2026-03-29T11:00:00+02:00"
    }

    Returns:
    - 201 with reservation data
    - 409 if time conflict
    - 400 if validation error
    """
    court_id = request.data.get('court_id')
    start_str = request.data.get('start')
    end_str = request.data.get('end')

    # Validation
    if not court_id or not start_str or not end_str:
        return Response(
            {'message': 'court_id, start and end are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        court = Court.objects.get(id=court_id, is_active=True)
    except Court.DoesNotExist:
        return Response(
            {'message': 'Court not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
    except ValueError:
        return Response(
            {'message': 'Invalid datetime format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if end > start
    if end_time <= start_time:
        return Response(
            {'message': 'End time must be after start time'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check for time conflicts
    conflicts = Reservation.objects.filter(
        court=court,
        status__in=['pending', 'confirmed']
    ).filter(
        Q(start_time__lt=end_time, end_time__gt=start_time)
    )

    if conflicts.exists():
        conflict_data = [
            {
                'court_id': c.court.id,
                'start': c.start_time.isoformat(),
                'end': c.end_time.isoformat()
            }
            for c in conflicts
        ]
        return Response(
            {
                'code': 'TIME_CONFLICT',
                'message': 'Wybrany termin nie jest już dostępny.',
                'conflicts': conflict_data
            },
            status=status.HTTP_409_CONFLICT
        )

    # Create reservation
    reservation = Reservation.objects.create(
        user=request.user,
        court=court,
        start_time=start_time,
        end_time=end_time,
        status='confirmed',
        notes=''
    )

    return Response(
        {
            'id': reservation.id,
            'court_id': court.id,
            'court_name': f"Kort {court.number}",
            'facility_id': court.facility.id,
            'facility_name': court.facility.name,
            'start': reservation.start_time.isoformat(),
            'end': reservation.end_time.isoformat(),
            'status': reservation.status,
            'reserved_by_me': True
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cancel_reservation(request, reservation_id):
    """
    Cancel a reservation
    DELETE /api/reservations/:id/
    """
    try:
        reservation = Reservation.objects.get(
            id=reservation_id,
            user=request.user
        )
    except Reservation.DoesNotExist:
        return Response(
            {'message': 'Reservation not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Only cancel future reservations
    if reservation.start_time < timezone.now():
        return Response(
            {'message': 'Cannot cancel past reservations'},
            status=status.HTTP_400_BAD_REQUEST
        )

    reservation.status = 'cancelled'
    reservation.save()

    return Response(status=status.HTTP_204_NO_CONTENT)
