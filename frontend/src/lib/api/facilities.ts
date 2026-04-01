/**
 * Facilities API
 */

import { api } from './client';
import type { Facility } from '../../types/facility';

/**
 * Get all facilities
 * GET /api/facilities/
 */
export const getFacilities = () => api<Facility[]>('/api/facilities/');
