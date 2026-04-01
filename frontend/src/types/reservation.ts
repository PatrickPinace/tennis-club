/**
 * Reservation types
 */

import type { Facility } from './facility';
import type { Court } from './court';

export type ReservationStatus = 'confirmed' | 'pending' | 'cancelled' | 'blocked';

export interface Reservation {
  id: number;
  court_id: number;
  court_name: string;
  facility_id: number;
  facility_name: string;
  start: string;
  end: string;
  status: ReservationStatus;
  reserved_by_me?: boolean;
}

export interface AvailabilitySlot {
  court_id: number;
  court_name: string;
  start: string;
  end: string;
  status: 'available' | 'booked' | 'blocked';
  reservation_id?: number;
  reserved_by_me?: boolean;
}

export interface AvailabilityResponse {
  date: string;
  facility: Facility;
  courts: Court[];
  slots: AvailabilitySlot[];
}

export interface CreateReservationPayload {
  court_id: number;
  start: string;
  end: string;
}

export interface ReservationConflict {
  court_id: number;
  start: string;
  end: string;
}

export interface ReservationErrorResponse {
  code: string;
  message: string;
  conflicts?: ReservationConflict[];
}
