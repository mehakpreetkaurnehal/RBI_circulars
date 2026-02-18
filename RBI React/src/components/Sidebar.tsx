import { useState } from "react";
import {
  MessageSquarePlus,
  History,
  Trash2,
  ChevronLeft,
  ChevronRight,
  MessageCircle,
  AlertTriangle,
} from "lucide-react";
import type { ChatSession } from "../types";
import { cn } from "../utils/cn";

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onClearAll: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onClearAll,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const reversedSessions = [...sessions].reverse();

  // Group sessions by date
  const today = new Date();
  const todayStr = today.toDateString();
  const yesterdayStr = new Date(today.getTime() - 86400000).toDateString();

  const groups: { label: string; items: ChatSession[] }[] = [];
  const todayItems: ChatSession[] = [];
  const yesterdayItems: ChatSession[] = [];
  const olderItems: ChatSession[] = [];

  for (const s of reversedSessions) {
    const dateStr = new Date(s.createdAt).toDateString();
    if (dateStr === todayStr) todayItems.push(s);
    else if (dateStr === yesterdayStr) yesterdayItems.push(s);
    else olderItems.push(s);
  }

  if (todayItems.length > 0) groups.push({ label: "Today", items: todayItems });
  if (yesterdayItems.length > 0) groups.push({ label: "Yesterday", items: yesterdayItems });
  if (olderItems.length > 0) groups.push({ label: "Older", items: olderItems });

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-slate-200 bg-slate-50 transition-all duration-300 h-screen",
        collapsed ? "w-16" : "w-72"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-200">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
              <History className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-slate-800 text-sm">Chat History</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors text-slate-500"
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className={cn(
            "flex items-center gap-2 w-full rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium transition-all hover:from-blue-700 hover:to-indigo-700 shadow-md shadow-blue-200 active:scale-[0.98]",
            collapsed ? "justify-center p-2.5" : "px-4 py-2.5 text-sm"
          )}
          title="New Chat"
        >
          <MessageSquarePlus className="h-4 w-4 shrink-0" />
          {!collapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {groups.length === 0 && !collapsed && (
          <div className="text-center text-slate-400 text-xs mt-8 px-4">
            No conversations yet. Start a new chat!
          </div>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mb-3">
            {!collapsed && (
              <div className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                {group.label}
              </div>
            )}
            {group.items.map((session) => (
              <div
                key={session.id}
                className={cn(
                  "group flex items-center rounded-lg cursor-pointer transition-all mb-0.5",
                  activeSessionId === session.id
                    ? "bg-blue-100 text-blue-800"
                    : "hover:bg-slate-200/70 text-slate-600"
                )}
              >
                <button
                  onClick={() => onSelectSession(session.id)}
                  className={cn(
                    "flex items-center gap-2 flex-1 min-w-0",
                    collapsed ? "justify-center p-2.5" : "px-2.5 py-2 text-left"
                  )}
                  title={session.title || "Untitled"}
                >
                  <MessageCircle
                    className={cn(
                      "h-3.5 w-3.5 shrink-0",
                      activeSessionId === session.id ? "text-blue-600" : "text-slate-400"
                    )}
                  />
                  {!collapsed && (
                    <span className="truncate text-sm">
                      {session.title || "Untitled"}
                    </span>
                  )}
                </button>
                {!collapsed && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 mr-1 rounded-md hover:bg-red-100 hover:text-red-600 transition-all"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Footer */}
      {sessions.length > 0 && !collapsed && (
        <div className="p-3 border-t border-slate-200">
          {showClearConfirm ? (
            <div className="flex items-center gap-2 text-xs">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              <span className="text-slate-600">Clear all?</span>
              <button
                onClick={() => {
                  onClearAll();
                  setShowClearConfirm(false);
                }}
                className="px-2 py-0.5 bg-red-500 text-white rounded-md hover:bg-red-600 transition"
              >
                Yes
              </button>
              <button
                onClick={() => setShowClearConfirm(false)}
                className="px-2 py-0.5 bg-slate-200 text-slate-600 rounded-md hover:bg-slate-300 transition"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowClearConfirm(true)}
              className="flex items-center gap-2 text-xs text-slate-400 hover:text-red-500 transition-colors w-full"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Clear all history</span>
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
