/**
 * ReservationsView - Main container for reservations module
 * Manages state for facility, date, courts, availability
 */

import { useState, useEffect } from 'react';
import type { Facility } from '../../types/facility';
import type { Court } from '../../types/court';
import type { AvailabilityResponse, Reservation } from '../../types/reservation';
import { getFacilities } from '../../lib/api/facilities';
import { getCourts } from '../../lib/api/courts';
import { getAvailability, getMyReservations, cancelReservation } from '../../lib/api/reservations';
import { formatDate } from '../../lib/utils/dates';
import ReservationFilters from './ReservationFilters';
import CourtCalendar from './CourtCalendar';
import ReservationModal from './ReservationModal';
import ReservationsList from './ReservationsList';

export default function ReservationsView() {
  // State
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [selectedFacilityId, setSelectedFacilityId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(formatDate(new Date()));
  const [selectedCourtId, setSelectedCourtId] = useState<number | null>(null);

  const [courts, setCourts] = useState<Court[]>([]);
  const [availability, setAvailability] = useState<AvailabilityResponse | null>(null);
  const [myReservations, setMyReservations] = useState<Reservation[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<{
    courtId: number;
    courtName: string;
    startTime: Date;
    endTime: Date;
  } | null>(null);

  // Load facilities on mount
  useEffect(() => {
    loadFacilities();
  }, []);

  // Load courts when facility changes
  useEffect(() => {
    if (selectedFacilityId) {
      loadCourts(selectedFacilityId);
    }
  }, [selectedFacilityId]);

  // Load availability when facility or date changes
  useEffect(() => {
    if (selectedFacilityId && selectedDate) {
      loadAvailability(selectedFacilityId, selectedDate);
      loadMyReservations(selectedDate);
    }
  }, [selectedFacilityId, selectedDate]);

  // API calls
  async function loadFacilities() {
    try {
      const data = await getFacilities();
      setFacilities(data);
      if (data.length > 0) {
        setSelectedFacilityId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load facilities:', err);
      setError('Nie udało się załadować obiektów');
    }
  }

  async function loadCourts(facilityId: number) {
    try {
      const data = await getCourts(facilityId);
      setCourts(data);
      setSelectedCourtId(null); // Reset court selection
    } catch (err) {
      console.error('Failed to load courts:', err);
      setError('Nie udało się załadować kortów');
    }
  }

  async function loadAvailability(facilityId: number, date: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await getAvailability(date, facilityId);
      setAvailability(data);
    } catch (err) {
      console.error('Failed to load availability:', err);
      setError('Nie udało się załadować dostępności');
    } finally {
      setLoading(false);
    }
  }

  async function loadMyReservations(fromDate: string) {
    try {
      const data = await getMyReservations(fromDate);
      setMyReservations(data);
    } catch (err) {
      console.error('Failed to load my reservations:', err);
    }
  }

  // Handlers
  const handleFacilityChange = (facilityId: number) => {
    setSelectedFacilityId(facilityId);
  };

  const handleDateChange = (date: string) => {
    setSelectedDate(date);
  };

  const handleCourtChange = (courtId: number | null) => {
    setSelectedCourtId(courtId);
  };

  const handleSlotClick = (start: Date, end: Date, courtId: number) => {
    // Find court name
    const court = courts.find(c => c.id === courtId);
    if (!court) {
      console.error('Court not found:', courtId);
      return;
    }

    setSelectedSlot({
      courtId,
      courtName: court.name,
      startTime: start,
      endTime: end
    });
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setSelectedSlot(null);
  };

  const handleReservationSuccess = () => {
    // Reload availability and my reservations after successful booking
    if (selectedFacilityId && selectedDate) {
      loadAvailability(selectedFacilityId, selectedDate);
      loadMyReservations(selectedDate);
    }
  };

  const handleCancelReservation = async (reservationId: number) => {
    await cancelReservation(reservationId);
    // Reload availability and my reservations after cancellation
    if (selectedFacilityId && selectedDate) {
      loadAvailability(selectedFacilityId, selectedDate);
      loadMyReservations(selectedDate);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--color-text-primary)]">
            Rezerwacje kortów
          </h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Sprawdź dostępność i zarezerwuj kort
          </p>
        </div>
      </div>

      {/* Filters */}
      <ReservationFilters
        facilities={facilities}
        selectedFacilityId={selectedFacilityId}
        selectedDate={selectedDate}
        selectedCourtId={selectedCourtId}
        courts={courts}
        onFacilityChange={handleFacilityChange}
        onDateChange={handleDateChange}
        onCourtChange={handleCourtChange}
      />

      {/* Error state */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      {/* Calendar */}
      {availability && (
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-[var(--color-text-primary)]">
              Kalendarz kortów
            </h3>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {availability.slots.length} rezerwacji na {selectedDate}
            </p>
          </div>
          <CourtCalendar
            availability={availability}
            selectedDate={selectedDate}
            loading={loading}
            onSlotClick={handleSlotClick}
          />
        </div>
      )}

      {/* My reservations list */}
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
        <h3 className="text-xl font-bold text-[var(--color-text-primary)] mb-4">
          Moje rezerwacje
        </h3>
        <ReservationsList
          reservations={myReservations}
          onCancel={handleCancelReservation}
        />
      </div>

      {/* Reservation Modal */}
      {selectedSlot && (
        <ReservationModal
          isOpen={isModalOpen}
          onClose={handleModalClose}
          courtId={selectedSlot.courtId}
          courtName={selectedSlot.courtName}
          startTime={selectedSlot.startTime}
          endTime={selectedSlot.endTime}
          onSuccess={handleReservationSuccess}
        />
      )}
    </div>
  );
}
