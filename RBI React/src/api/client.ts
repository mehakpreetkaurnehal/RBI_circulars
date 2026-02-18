const API_BASE_URL = "http://localhost:8000";

interface AskResponse {
  question: string;
  answer: string;
  sources: Record<string, string>;
}

interface HistorySession {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: {
    id: number;
    question: string;
    answer: string;
    sources: Record<string, string>;
    created_at: string;
  }[];
}

interface HealthResponse {
  status: string;
  chunks_loaded: number;
  model: string;
}

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async healthCheck(): Promise<HealthResponse> {
    const res = await fetch(`${this.baseUrl}/api/health`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  }

  async ask(
    question: string,
    sessionId: string,
    history: { question: string; answer: string }[]
  ): Promise<AskResponse> {
    const res = await fetch(`${this.baseUrl}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        history: history.slice(-3), // last 3 for context
      }),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed: ${res.status}`);
    }
    return res.json();
  }

  async getSessions(): Promise<HistorySession[]> {
    const res = await fetch(`${this.baseUrl}/api/sessions`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
    return res.json();
  }

  async getSession(sessionId: string): Promise<HistorySession> {
    const res = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to fetch session: ${res.status}`);
    return res.json();
  }

  async deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to delete session: ${res.status}`);
  }

  async clearAllSessions(): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/sessions`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to clear sessions: ${res.status}`);
  }
}

export const apiClient = new APIClient();
export type { AskResponse, HistorySession, HealthResponse };
