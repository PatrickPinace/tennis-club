/**
 * Dashboard API functions
 */

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'https://tennis.mediprima.pl');

export interface DashboardStats {
  user_stats: {
    total_matches: number;
    wins: number;
    losses: number;
    win_rate: number;
  };
  ranking: {
    position: number;
    elo_rating: number;
    ranking_points: number;
    top_percentage: number;
  };
  next_reservation: {
    id: number;
    date: string;
    time: string;
    court: {
      number: number;
      surface: string;
      facility: string;
    };
    status: string;
  } | null;
  last_match: {
    id: number;
    date: string;
    opponent: string;
    result: 'won' | 'lost';
    score: string;
    location: string;
  } | null;
  upcoming_tournament: {
    id: number;
    name: string;
    date_range: string;
    status: string;
    participant_status: string;
  } | null;
  recent_activity: Array<{
    id: number;
    type: string;
    title: string;
    message: string;
    is_read: boolean;
    created_at: string;
  }>;
}

/**
 * Get dashboard statistics
 * GET /api/dashboard/stats/
 * Requires authentication
 */
export async function getDashboardStats(sessionId: string): Promise<DashboardStats | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/dashboard/stats/`, {
      headers: {
        Cookie: `sessionid=${sessionId}`,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Dashboard stats fetch failed:', error);
    return null;
  }
}
