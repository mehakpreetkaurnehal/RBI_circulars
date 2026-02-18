export interface ChatMessage {
  id: string;
  question: string;
  answer: string;
  sources: Record<string, string>; // url -> title
  createdAt: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

export interface APIConfig {
  baseUrl: string;
  connected: boolean;
  error: string | null;
}
