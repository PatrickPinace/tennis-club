/**
 * ReservationsList - Enhanced list of user's reservations
 * Shows upcoming reservations with cancel functionality
 */

import { useState } from 'react';
import Button from '../ui/Button';
import type { Reservation } from '../../types/reservation';

interface ReservationsListProps {
  reservations: Reservation[];
  onCancel: (reservationId: number) => Promise<void>;
}

export default function ReservationsList({
  reservations,
  onCancel
}: ReservationsListProps) {
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  const [confirmCancelId, setConfirmCancelId] = useState<number | null>(null);

  const handleCancelClick = (reservationId: number) => {
    setConfirmCancelId(reservationId);
  };

  const handleConfirmCancel = async (reservationId: number) => {
    setCancelingId(reservationId);
    try {
      await onCancel(reservationId);
      setConfirmCancelId(null);
    } catch (error) {
      console.error('Failed to cancel reservation:', error);
      alert('Nie udało się anulować rezerwacji. Spróbuj ponownie.');
    } finally {
      setCancelingId(null);
    }
  };

  const handleCancelConfirmDialog = () => {
    setConfirmCancelId(null);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('pl-PL', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('pl-PL', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getDuration = (start: string, end: string) => {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffMs = endDate.getTime() - startDate.getTime();
    const diffMins = Math.floor(diffMs / 1000 / 60);
    const hours = Math.floor(diffMins / 60);
    const minutes = diffMins % 60;

    if (hours > 0 && minutes > 0) {
      return `${hours}h ${minutes}min`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else {
      return `${minutes}min`;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'confirmed':
        return 'bg-green-100 text-green-700';
      case 'pending':
        return 'bg-yellow-100 text-yellow-700';
      case 'cancelled':
        return 'bg-gray-100 text-gray-700';
      default:
        return 'bg-blue-100 text-blue-700';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'confirmed':
        return 'Potwierdzona';
      case 'pending':
        return 'Oczekująca';
      case 'cancelled':
        return 'Anulowana';
      default:
        return status;
    }
  };

  const isPastReservation = (endTime: string) => {
    return new Date(endTime) < new Date();
  };

  const canCancel = (reservation: Reservation) => {
    return reservation.status === 'confirmed' && !isPastReservation(reservation.end);
  };

  if (reservations.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[var(--color-bg-secondary)] mb-4">
          <svg className="w-8 h-8 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <p className="text-[var(--color-text-secondary)] text-sm">
          Nie masz jeszcze żadnych rezerwacji
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {reservations.map((reservation) => (
        <div
          key={reservation.id}
          className={`p-4 rounded-lg border transition-all ${
            isPastReservation(reservation.end)
              ? 'bg-gray-50 border-gray-200 opacity-60'
              : 'bg-white border-[var(--color-border)] hover:shadow-sm'
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            {/* Left side - Details */}
            <div className="flex-1 min-w-0">
              {/* Court and Facility */}
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 bg-[var(--color-secondary)] rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                  🎾
                </div>
                <div className="min-w-0">
                  <h4 className="font-semibold text-[var(--color-text-primary)] truncate">
                    {reservation.court_name}
                  </h4>
                  <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                    {reservation.facility_name}
                  </p>
                </div>
              </div>

              {/* Date and Time */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[var(--color-text-secondary)]">
                <div className="flex items-center gap-1.5">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <span>{formatDate(reservation.start)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>
                    {formatTime(reservation.start)} - {formatTime(reservation.end)}
                  </span>
                  <span className="text-[var(--color-text-tertiary)]">
                    ({getDuration(reservation.start, reservation.end)})
                  </span>
                </div>
              </div>
            </div>

            {/* Right side - Status and Actions */}
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              <span className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(reservation.status)}`}>
                {getStatusLabel(reservation.status)}
              </span>

              {/* Cancel button */}
              {canCancel(reservation) && (
                <div>
                  {confirmCancelId === reservation.id ? (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCancelConfirmDialog}
                        className="px-2 py-1 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
                        disabled={cancelingId === reservation.id}
                      >
                        Nie
                      </button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleConfirmCancel(reservation.id)}
                        disabled={cancelingId === reservation.id}
                        className="text-xs"
                      >
                        {cancelingId === reservation.id ? (
                          <>
                            <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin mr-1"></div>
                            Anulowanie...
                          </>
                        ) : (
                          'Tak, anuluj'
                        )}
                      </Button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleCancelClick(reservation.id)}
                      className="text-xs text-red-600 hover:text-red-700 font-medium transition-colors"
                      disabled={cancelingId !== null}
                    >
                      Anuluj rezerwację
                    </button>
                  )}
                </div>
              )}

              {isPastReservation(reservation.end) && (
                <span className="text-xs text-[var(--color-text-tertiary)]">
                  Zakończona
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
