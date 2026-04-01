/**
 * Tournaments API client (Full Implementation)
 */

import { api } from './client';
import type {
  TournamentsListResponse,
  TournamentDetail,
  TournamentStatus,
  RegisterForTournamentPayload,
  CreateTournamentPayload,
  ReportMatchResultPayload,
  BracketResponse
} from '../../types/tournament';

// ============================================================================
// Tournament CRUD
// ============================================================================

/**
 * Get list of tournaments
 */
export const getTournaments = (params?: {
  status?: TournamentStatus;
  my?: boolean;
  limit?: number;
}): Promise<TournamentsListResponse> => {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append('status', params.status);
  if (params?.my) queryParams.append('my', 'true');
  if (params?.limit) queryParams.append('limit', params.limit.toString());

  const query = queryParams.toString();
  return api<TournamentsListResponse>(`/api/tournaments/${query ? `?${query}` : ''}`);
};

/**
 * Create new tournament (managers only)
 */
export const createTournament = (payload: CreateTournamentPayload): Promise<{ id: number; name: string; status: string; message: string }> => {
  // Convert datetime-local format to ISO format for backend
  const formattedPayload = {
    ...payload,
    start_date: new Date(payload.start_date).toISOString(),
    end_date: new Date(payload.end_date).toISOString(),
    registration_deadline: new Date(payload.registration_deadline).toISOString()
  };

  return api<{ id: number; name: string; status: string; message: string }>('/api/tournaments/', {
    method: 'POST',
    body: JSON.stringify(formattedPayload)
  });
};

/**
 * Get tournament details by ID
 */
export const getTournamentDetail = (tournamentId: number): Promise<TournamentDetail> => {
  return api<TournamentDetail>(`/api/tournaments/${tournamentId}/`);
};

/**
 * Get tournament bracket
 */
export const getTournamentBracket = (tournamentId: number): Promise<BracketResponse> => {
  return api<BracketResponse>(`/api/tournaments/${tournamentId}/bracket/`);
};

// ============================================================================
// Tournament Management Actions (Managers Only)
// ============================================================================

/**
 * Open tournament registration
 */
export const openRegistration = (tournamentId: number): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/open-registration/`, {
    method: 'POST'
  });
};

/**
 * Close tournament registration
 */
export const closeRegistration = (tournamentId: number): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/close-registration/`, {
    method: 'POST'
  });
};

/**
 * Confirm participants (finalize roster)
 */
export const confirmParticipants = (tournamentId: number): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/confirm-participants/`, {
    method: 'POST'
  });
};

/**
 * Generate bracket
 */
export const generateBracket = (tournamentId: number): Promise<{ message: string; num_matches: number }> => {
  return api<{ message: string; num_matches: number }>(`/api/tournaments/${tournamentId}/generate-bracket/`, {
    method: 'POST'
  });
};

/**
 * Start tournament
 */
export const startTournament = (tournamentId: number): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/start/`, {
    method: 'POST'
  });
};

/**
 * Finish tournament
 */
export const finishTournament = (tournamentId: number): Promise<{ message: string; winner?: string }> => {
  return api<{ message: string; winner?: string }>(`/api/tournaments/${tournamentId}/finish/`, {
    method: 'POST'
  });
};

/**
 * Cancel tournament
 */
export const cancelTournament = (tournamentId: number, reason?: string): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/cancel/`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || '' })
  });
};

/**
 * Approve or reject participant
 */
export const approveParticipant = (tournamentId: number, participantId: number, approved: boolean): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/approve-participant/`, {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId, approved })
  });
};

// ============================================================================
// User Participation
// ============================================================================

/**
 * Join tournament
 */
export const joinTournament = (tournamentId: number): Promise<{ id: number; status: string; message: string }> => {
  return api<{ id: number; status: string; message: string }>(`/api/tournaments/${tournamentId}/join/`, {
    method: 'POST'
  });
};

/**
 * Withdraw from tournament
 */
export const withdrawFromTournament = (tournamentId: number, reason?: string): Promise<{ message: string }> => {
  return api<{ message: string }>(`/api/tournaments/${tournamentId}/withdraw/`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || '' })
  });
};

// ============================================================================
// Match Management
// ============================================================================

/**
 * Report match result
 */
export const reportMatchResult = (matchId: number, result: ReportMatchResultPayload): Promise<{ message: string; winner: string }> => {
  return api<{ message: string; winner: string }>(`/api/tournament-matches/${matchId}/report-result/`, {
    method: 'POST',
    body: JSON.stringify(result)
  });
};

// Legacy endpoints (kept for compatibility with old code)
export const registerForTournament = joinTournament;
