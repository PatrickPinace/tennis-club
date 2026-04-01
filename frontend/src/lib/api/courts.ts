/**
 * Courts API
 */

import { api } from './client';
import type { Court } from '../../types/court';

/**
 * Get courts for a facility
 * GET /api/courts/?facility_id=1
 */
export const getCourts = (facilityId: number) =>
  api<Court[]>(`/api/courts/?facility_id=${facilityId}`);
