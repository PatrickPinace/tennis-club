from rest_framework import serializers
from apps.courts.models import Reservation, TennisFacility


class MyReservationSerializer(serializers.ModelSerializer):
    court_name = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = ['id', 'court_name', 'facility_name', 'start_time', 'end_time', 'status']

    def get_court_name(self, obj):
        if obj.court:
            return f"Kort {obj.court.court_number}"
        return None

    def get_facility_name(self, obj):
        if obj.court and obj.court.facility:
            return obj.court.facility.name
        return None


class FacilityListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TennisFacility
        fields = ['id', 'name', 'address']
