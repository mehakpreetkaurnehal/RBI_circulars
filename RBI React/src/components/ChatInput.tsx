import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (query: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [query, setQuery] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [query]);

  const handleSubmit = () => {
    if (query.trim() && !isLoading) {
      onSend(query.trim());
      setQuery("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white/80 backdrop-blur-lg p-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-3 bg-white border border-slate-200 rounded-2xl px-4 py-3 shadow-lg shadow-slate-100 focus-within:border-blue-400 focus-within:shadow-blue-100 transition-all">
          <textarea
            ref={textareaRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about RBI circulars, regulations, guidelines..."
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none bg-transparent text-slate-800 placeholder-slate-400 text-sm leading-relaxed focus:outline-none disabled:opacity-50 min-h-[24px] max-h-[150px]"
          />
          <button
            onClick={handleSubmit}
            disabled={!query.trim() || isLoading}
            className="flex items-center justify-center h-9 w-9 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:from-blue-700 hover:to-indigo-700 transition-all active:scale-95 shrink-0 shadow-md shadow-blue-200"
            title="Send message"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="text-center text-[11px] text-slate-400 mt-2">
          Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono">Enter</kbd> to send, <kbd className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}
