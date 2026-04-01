/**
 * ReservationModal - Modal for creating a new court reservation
 */

import { useState } from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import { createReservation } from '../../lib/api/reservations';
import type { CreateReservationPayload } from '../../types/reservation';

interface ReservationModalProps {
  isOpen: boolean;
  onClose: () => void;
  courtId: number;
  courtName: string;
  startTime: Date;
  endTime: Date;
  onSuccess: () => void;
}

export default function ReservationModal({
  isOpen,
  onClose,
  courtId,
  courtName,
  startTime,
  endTime,
  onSuccess
}: ReservationModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatDateTime = (date: Date) => {
    return date.toLocaleString('pl-PL', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('pl-PL', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getDuration = () => {
    const diff = endTime.getTime() - startTime.getTime();
    const minutes = Math.floor(diff / 1000 / 60);
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours > 0 && remainingMinutes > 0) {
      return `${hours}h ${remainingMinutes}min`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else {
      return `${remainingMinutes}min`;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload: CreateReservationPayload = {
        court_id: courtId,
        start: startTime.toISOString(),
        end: endTime.toISOString()
      };

      await createReservation(payload);
      onSuccess();
      onClose();
    } catch (err) {
      console.error('Failed to create reservation:', err);
      setError('Nie udało się utworzyć rezerwacji. Spróbuj ponownie.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setError(null);
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Nowa rezerwacja" size="md">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Reservation details */}
        <div className="space-y-4">
          {/* Court */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-2">
              Kort
            </label>
            <div className="flex items-center gap-3 p-4 bg-[var(--color-bg-secondary)] rounded-lg">
              <div className="w-10 h-10 bg-[var(--color-secondary)] rounded-lg flex items-center justify-center text-white font-bold">
                🎾
              </div>
              <div>
                <p className="font-semibold text-[var(--color-text-primary)]">
                  {courtName}
                </p>
              </div>
            </div>
          </div>

          {/* Date & Time */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-2">
              Data i godzina
            </label>
            <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <svg
                  className="w-5 h-5 text-[var(--color-secondary)]"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                <span className="text-[var(--color-text-primary)] font-medium">
                  {formatDateTime(startTime)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <svg
                  className="w-5 h-5 text-[var(--color-secondary)]"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span className="text-[var(--color-text-primary)]">
                  {formatTime(startTime)} - {formatTime(endTime)}
                </span>
                <span className="ml-auto text-[var(--color-text-tertiary)]">
                  ({getDuration()})
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--color-border)]">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={loading}
          >
            Anuluj
          </Button>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                Tworzenie...
              </>
            ) : (
              'Zarezerwuj kort'
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
