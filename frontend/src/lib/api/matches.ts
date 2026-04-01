/**
 * Matches API client (Sprint 4)
 */

import { api } from './client';
import type {
  MatchesListResponse,
  MatchDetail,
  CreateMatchPayload,
  UpdateMatchPayload,
  MatchStatus
} from '../../types/match';

/**
 * Get list of matches for authenticated user
 */
export const getMatches = (params?: {
  status?: MatchStatus;
  limit?: number;
}): Promise<MatchesListResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append('status', params.status);
  if (params?.limit) queryParams.append('limit', params.limit.toString());

  const query = queryParams.toString();
  return api<MatchesListResponse>(`/api/matches/${query ? `?${query}` : ''}`);
};

/**
 * Get match details by ID
 */
export const getMatchDetail = (matchId: number): Promise<MatchDetail> => {
  return api<MatchDetail>(`/api/matches/${matchId}/`);
};

/**
 * Create a new match
 */
export const createMatch = (payload: CreateMatchPayload): Promise<{ id: number; message: string }> => {
  return api<{ id: number; message: string }>('/api/matches/create/', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
};

/**
 * Update match result (sets and status)
 */
export const updateMatchResult = (
  matchId: number,
  payload: UpdateMatchPayload
): Promise<{ id: number; message: string; winner_side: 'p1' | 'p2' | null }> => {
  return api<{ id: number; message: string; winner_side: 'p1' | 'p2' | null }>(
    `/api/matches/${matchId}/update/`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }
  );
};

/**
 * Cancel a match
 */
export const cancelMatch = (matchId: number): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/matches/${matchId}/cancel/`, {
    method: 'DELETE'
  });
};
