import { useState, useCallback, useEffect, useRef } from "react";
import type { ChatSession, ChatMessage } from "../types";
import { apiClient } from "../api/client";

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function useChatStore() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState<boolean | null>(null); // null = checking
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [serverInfo, setServerInfo] = useState<string>("");
  const hasLoadedRef = useRef(false);

  // Check backend connection & load sessions on mount
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    async function init() {
      try {
        const health = await apiClient.healthCheck();
        setIsConnected(true);
        setConnectionError(null);
        setServerInfo(`${health.chunks_loaded} chunks loaded • ${health.model}`);

        // Load sessions from backend
        const backendSessions = await apiClient.getSessions();
        const mapped: ChatSession[] = backendSessions.map((s) => ({
          id: s.session_id,
          title: s.title,
          createdAt: s.created_at,
          updatedAt: s.updated_at,
          messages: s.messages.map((m) => ({
            id: String(m.id),
            question: m.question,
            answer: m.answer,
            sources: m.sources,
            createdAt: m.created_at,
          })),
        }));
        setSessions(mapped);
        if (mapped.length > 0) {
          setActiveSessionId(mapped[mapped.length - 1].id);
        }
      } catch (err) {
        setIsConnected(false);
        setConnectionError(
          err instanceof Error ? err.message : "Cannot connect to backend"
        );
      }
    }

    init();
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;

  const refreshSessions = useCallback(async () => {
    try {
      const backendSessions = await apiClient.getSessions();
      const mapped: ChatSession[] = backendSessions.map((s) => ({
        id: s.session_id,
        title: s.title,
        createdAt: s.created_at,
        updatedAt: s.updated_at,
        messages: s.messages.map((m) => ({
          id: String(m.id),
          question: m.question,
          answer: m.answer,
          sources: m.sources,
          createdAt: m.created_at,
        })),
      }));
      setSessions(mapped);
    } catch {
      // silently fail
    }
  }, []);

  const createNewChat = useCallback(() => {
    const newSession: ChatSession = {
      id: generateId(),
      title: "New Chat",
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setSessions((prev) => [...prev, newSession]);
    setActiveSessionId(newSession.id);
  }, []);

  const selectSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      try {
        await apiClient.deleteSession(id);
      } catch {
        // continue with local delete
      }
      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== id);
        if (activeSessionId === id) {
          setActiveSessionId(
            filtered.length > 0 ? filtered[filtered.length - 1].id : null
          );
        }
        return filtered;
      });
    },
    [activeSessionId]
  );

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim() || !isConnected) return;

      let sessionId = activeSessionId;
      let currentMessages: ChatMessage[] = [];

      // If no active session, create one
      if (!sessionId) {
        const newSession: ChatSession = {
          id: generateId(),
          title: query.slice(0, 50),
          messages: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        setSessions((prev) => [...prev, newSession]);
        sessionId = newSession.id;
        setActiveSessionId(newSession.id);
      } else {
        const session = sessions.find((s) => s.id === sessionId);
        currentMessages = session?.messages ?? [];
      }

      const targetSessionId = sessionId;

      setIsLoading(true);

      try {
        // Build history context for follow-up questions
        const history = currentMessages.map((m) => ({
          question: m.question,
          answer: m.answer,
        }));

        // Call the actual backend API
        const result = await apiClient.ask(query, targetSessionId, history);

        const newMessage: ChatMessage = {
          id: generateId(),
          question: result.question,
          answer: result.answer,
          sources: result.sources,
          createdAt: new Date().toISOString(),
        };

        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === targetSessionId) {
              return {
                ...s,
                title:
                  s.messages.length === 0 ? query.slice(0, 50) : s.title,
                messages: [...s.messages, newMessage],
                updatedAt: new Date().toISOString(),
              };
            }
            return s;
          })
        );

        // Refresh from backend to stay in sync
        await refreshSessions();
      } catch (err) {
        // Show error as a message
        const errorMessage: ChatMessage = {
          id: generateId(),
          question: query,
          answer: `**Error:** ${err instanceof Error ? err.message : "Failed to get response from backend. Please check if the server is running."}`,
          sources: {},
          createdAt: new Date().toISOString(),
        };

        setSessions((prev) =>
          prev.map((s) => {
            if (s.id === targetSessionId) {
              return {
                ...s,
                title:
                  s.messages.length === 0 ? query.slice(0, 50) : s.title,
                messages: [...s.messages, errorMessage],
                updatedAt: new Date().toISOString(),
              };
            }
            return s;
          })
        );
      } finally {
        setIsLoading(false);
      }
    },
    [activeSessionId, sessions, isConnected, refreshSessions]
  );

  const clearAllHistory = useCallback(async () => {
    try {
      await apiClient.clearAllSessions();
    } catch {
      // continue with local clear
    }
    setSessions([]);
    setActiveSessionId(null);
  }, []);

  const retryConnection = useCallback(async () => {
    setIsConnected(null);
    setConnectionError(null);
    try {
      const health = await apiClient.healthCheck();
      setIsConnected(true);
      setServerInfo(`${health.chunks_loaded} chunks loaded • ${health.model}`);
      await refreshSessions();
    } catch (err) {
      setIsConnected(false);
      setConnectionError(
        err instanceof Error ? err.message : "Cannot connect to backend"
      );
    }
  }, [refreshSessions]);

  return {
    sessions,
    activeSession,
    activeSessionId,
    isLoading,
    isConnected,
    connectionError,
    serverInfo,
    createNewChat,
    selectSession,
    deleteSession,
    sendMessage,
    clearAllHistory,
    retryConnection,
  };
}
