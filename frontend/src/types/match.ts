// Match types (Sprint 4)

export type MatchStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
export type MatchResult = 'won' | 'lost' | null;

export interface MatchSet {
  p1: number;
  p2: number;
}

export interface MatchCourt {
  id: number;
  name: string;
  surface: string;
  facility: string;
}

export interface MatchPlayer {
  id: number;
  username: string;
  full_name: string;
}

export interface MatchListItem {
  id: number;
  date: string;
  status: MatchStatus;
  is_doubles: boolean;
  opponent: string;
  result: MatchResult;
  sets: MatchSet[];
  court: MatchCourt | null;
  description: string;
}

export interface MatchDetail {
  id: number;
  date: string;
  status: MatchStatus;
  is_doubles: boolean;
  players: {
    player1: MatchPlayer;
    player2: MatchPlayer;
    player3?: MatchPlayer | null;
    player4?: MatchPlayer | null;
  };
  result: MatchResult;
  winner_side: 'p1' | 'p2' | null;
  sets: MatchSet[];
  court: MatchCourt | null;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface MatchesListResponse {
  matches: MatchListItem[];
  count: number;
}

export interface CreateMatchPayload {
  player2_id: number;
  player3_id?: number;
  player4_id?: number;
  match_date: string;
  court_id?: number;
  description?: string;
}

export interface UpdateMatchPayload {
  status?: MatchStatus;
  set1_p1?: number | null;
  set1_p2?: number | null;
  set2_p1?: number | null;
  set2_p2?: number | null;
  set3_p1?: number | null;
  set3_p2?: number | null;
}
