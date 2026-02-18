import { useRef, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatMessageComponent } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { LoadingIndicator } from "./components/LoadingIndicator";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { useChatStore } from "./hooks/useChatStore";

export function App() {
  const {
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
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeSession?.messages, isLoading]);

  const hasMessages = activeSession && activeSession.messages.length > 0;
  const showMainChat = isConnected === true;

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 overflow-hidden">
      {/* Sidebar - show always when connected */}
      {showMainChat && (
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewChat={createNewChat}
          onSelectSession={selectSession}
          onDeleteSession={deleteSession}
          onClearAll={clearAllHistory}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-white/70 backdrop-blur-lg">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-sm">
              <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-800">RBI Circular QA Assistant</h1>
              <p className="text-[11px] text-slate-400">Hybrid RAG • FAISS + BM25 • Cross-Encoder Reranking • Gemini</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isConnected === true && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-medium border border-emerald-100">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Connected
              </span>
            )}
            {isConnected === false && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 text-red-700 text-[11px] font-medium border border-red-100">
                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                Disconnected
              </span>
            )}
            {activeSession && (
              <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-[11px] font-medium border border-slate-200">
                {activeSession.messages.length} message{activeSession.messages.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </header>

        {/* Content Area */}
        {!showMainChat ? (
          <ConnectionStatus
            isConnected={isConnected}
            error={connectionError}
            onRetry={retryConnection}
          />
        ) : (
          <>
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto">
              {hasMessages ? (
                <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
                  {activeSession.messages.map((msg) => (
                    <ChatMessageComponent key={msg.id} message={msg} />
                  ))}
                  {isLoading && <LoadingIndicator />}
                  <div ref={messagesEndRef} />
                </div>
              ) : (
                <WelcomeScreen
                  onSuggestionClick={(query) => {
                    sendMessage(query);
                  }}
                  serverInfo={serverInfo}
                />
              )}
            </div>

            {/* Input Area */}
            <ChatInput onSend={sendMessage} isLoading={isLoading} />
          </>
        )}
      </div>
    </div>
  );
}
