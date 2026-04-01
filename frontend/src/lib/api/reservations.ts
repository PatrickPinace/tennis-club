/**
 * Reservations API
 */

import { api } from './client';
import type {
  AvailabilityResponse,
  Reservation,
  CreateReservationPayload
} from '../../types/reservation';

/**
 * Get availability for a specific date and facility
 * GET /api/reservations/availability/?date=2026-03-29&facility_id=1
 */
export const getAvailability = (date: string, facilityId: number) =>
  api<AvailabilityResponse>(
    `/api/reservations/availability/?date=${date}&facility_id=${facilityId}`
  );

/**
 * Get user's reservations from a specific date
 * GET /api/reservations/my/?from=2026-03-29
 */
export const getMyReservations = (from: string) =>
  api<Reservation[]>(`/api/reservations/my/?from=${from}`);

/**
 * Create a new reservation
 * POST /api/reservations/
 */
export const createReservation = (payload: CreateReservationPayload) =>
  api<Reservation>('/api/reservations/', {
    method: 'POST',
    body: JSON.stringify(payload)
  });

/**
 * Cancel a reservation
 * DELETE /api/reservations/:id/
 */
export const cancelReservation = (id: number) =>
  api<void>(`/api/reservations/${id}/`, {
    method: 'DELETE'
  });
