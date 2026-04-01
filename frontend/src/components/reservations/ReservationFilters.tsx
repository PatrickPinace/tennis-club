/**
 * ReservationFilters - Filter controls for facility, date, and court
 */

import type { Facility } from '../../types/facility';
import type { Court } from '../../types/court';

interface ReservationFiltersProps {
  facilities: Facility[];
  selectedFacilityId: number | null;
  selectedDate: string;
  selectedCourtId: number | null;
  courts: Court[];
  onFacilityChange: (facilityId: number) => void;
  onDateChange: (date: string) => void;
  onCourtChange: (courtId: number | null) => void;
}

export default function ReservationFilters({
  facilities,
  selectedFacilityId,
  selectedDate,
  selectedCourtId,
  courts,
  onFacilityChange,
  onDateChange,
  onCourtChange,
}: ReservationFiltersProps) {
  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Facility selector */}
        <div>
          <label
            htmlFor="facility"
            className="block text-sm font-medium text-[var(--color-text-primary)] mb-2"
          >
            Obiekt
          </label>
          <select
            id="facility"
            value={selectedFacilityId || ''}
            onChange={(e) => onFacilityChange(Number(e.target.value))}
            className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)] focus:border-transparent"
          >
            {facilities.length === 0 && (
              <option value="">Ładowanie...</option>
            )}
            {facilities.map((facility) => (
              <option key={facility.id} value={facility.id}>
                {facility.name} {facility.city && `(${facility.city})`}
              </option>
            ))}
          </select>
        </div>

        {/* Date picker */}
        <div>
          <label
            htmlFor="date"
            className="block text-sm font-medium text-[var(--color-text-primary)] mb-2"
          >
            Data
          </label>
          <input
            type="date"
            id="date"
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)] focus:border-transparent"
          />
        </div>

        {/* Court selector (optional - show all courts if null) */}
        <div>
          <label
            htmlFor="court"
            className="block text-sm font-medium text-[var(--color-text-primary)] mb-2"
          >
            Kort
          </label>
          <select
            id="court"
            value={selectedCourtId || ''}
            onChange={(e) => onCourtChange(e.target.value ? Number(e.target.value) : null)}
            className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)] focus:border-transparent"
            disabled={courts.length === 0}
          >
            <option value="">Wszystkie korty</option>
            {courts.map((court) => (
              <option key={court.id} value={court.id}>
                {court.name} ({court.surface})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Quick date navigation */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-[var(--color-border)]">
        <button
          onClick={() => {
            const yesterday = new Date(selectedDate);
            yesterday.setDate(yesterday.getDate() - 1);
            onDateChange(yesterday.toISOString().split('T')[0]);
          }}
          className="px-3 py-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)] rounded-lg transition"
        >
          ← Wczoraj
        </button>
        <button
          onClick={() => {
            const today = new Date();
            onDateChange(today.toISOString().split('T')[0]);
          }}
          className="px-3 py-1 text-sm font-medium text-[var(--color-secondary)] hover:bg-[var(--color-bg-secondary)] rounded-lg transition"
        >
          Dzisiaj
        </button>
        <button
          onClick={() => {
            const tomorrow = new Date(selectedDate);
            tomorrow.setDate(tomorrow.getDate() + 1);
            onDateChange(tomorrow.toISOString().split('T')[0]);
          }}
          className="px-3 py-1 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)] rounded-lg transition"
        >
          Jutro →
        </button>
      </div>
    </div>
  );
}
