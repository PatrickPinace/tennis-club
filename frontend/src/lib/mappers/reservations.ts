/**
 * Reservation mappers
 * Convert backend DTOs to FullCalendar events
 */

import type { AvailabilityResponse } from '../../types/reservation';

export function mapAvailabilityToEvents(data: AvailabilityResponse) {
  return data.slots
    .filter((slot) => slot.status !== 'available')
    .map((slot) => ({
      id: slot.reservation_id ? String(slot.reservation_id) : `${slot.court_id}-${slot.start}`,
      title: slot.court_name,
      start: slot.start,
      end: slot.end,
      extendedProps: {
        courtId: slot.court_id,
        status: slot.status,
        reservedByMe: slot.reserved_by_me ?? false
      },
      classNames: [
        slot.status === 'booked' ? 'fc-booked' : '',
        slot.status === 'blocked' ? 'fc-blocked' : '',
        slot.reserved_by_me ? 'fc-my-reservation' : ''
      ].filter(Boolean)
    }));
}
