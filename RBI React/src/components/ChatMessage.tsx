import { useState } from "react";
import {
  User,
  Bot,
  FileText,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../types";

interface ChatMessageProps {
  message: ChatMessageType;
}

function MarkdownText({ text }: { text: string }) {
  // Simple markdown-like rendering
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let listType: "ordered" | "unordered" | null = null;

  const flushList = (index: number) => {
    if (listItems.length > 0 && listType) {
      if (listType === "ordered") {
        elements.push(
          <ol key={`ol-${index}`} className="list-decimal list-inside space-y-1 my-2 ml-1">
            {listItems.map((item, i) => (
              <li key={i} className="text-slate-700">
                <InlineFormat text={item} />
              </li>
            ))}
          </ol>
        );
      } else {
        elements.push(
          <ul key={`ul-${index}`} className="list-disc list-inside space-y-1 my-2 ml-1">
            {listItems.map((item, i) => (
              <li key={i} className="text-slate-700">
                <InlineFormat text={item} />
              </li>
            ))}
          </ul>
        );
      }
      listItems = [];
      listType = null;
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Ordered list
    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)/);
    if (orderedMatch) {
      if (listType !== "ordered") flushList(index);
      listType = "ordered";
      listItems.push(orderedMatch[1]);
      return;
    }

    // Unordered list
    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)/);
    if (unorderedMatch) {
      if (listType !== "unordered") flushList(index);
      listType = "unordered";
      listItems.push(unorderedMatch[1]);
      return;
    }

    flushList(index);

    if (trimmed === "") {
      elements.push(<div key={index} className="h-2" />);
      return;
    }

    elements.push(
      <p key={index} className="text-slate-700 leading-relaxed">
        <InlineFormat text={trimmed} />
      </p>
    );
  });

  flushList(lines.length);

  return <div className="space-y-1">{elements}</div>;
}

function InlineFormat({ text }: { text: string }) {
  // Handle **bold**, *italic*, `code`, and [n] citations
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[(\d+)\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(
        <strong key={match.index} className="font-semibold text-slate-900">
          {match[2]}
        </strong>
      );
    } else if (match[3]) {
      parts.push(
        <em key={match.index} className="italic">
          {match[3]}
        </em>
      );
    } else if (match[4]) {
      parts.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 rounded bg-slate-100 text-blue-700 text-[13px] font-mono"
        >
          {match[4]}
        </code>
      );
    } else if (match[5]) {
      parts.push(
        <sup
          key={match.index}
          className="inline-flex items-center justify-center h-4 min-w-[16px] px-1 rounded bg-blue-100 text-blue-700 text-[10px] font-bold ml-0.5 cursor-default"
          title={`Source ${match[5]}`}
        >
          {match[5]}
        </sup>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <>{parts}</>;
}

export function ChatMessageComponent({ message }: ChatMessageProps) {
  const [showSources, setShowSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const sourceEntries = Object.entries(message.sources);
  const hasSources = sourceEntries.length > 0;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4 py-2">
      {/* Question */}
      <div className="flex gap-3 justify-end">
        <div className="max-w-[75%] bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-2xl rounded-tr-md px-4 py-3 shadow-md shadow-blue-100">
          <p className="text-sm leading-relaxed">{message.question}</p>
        </div>
        <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mt-1">
          <User className="h-4 w-4 text-blue-700" />
        </div>
      </div>

      {/* Answer */}
      <div className="flex gap-3">
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shrink-0 mt-1 shadow-sm">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
            <MarkdownText text={message.answer} />

            {/* Action bar */}
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors px-2 py-1 rounded-md hover:bg-slate-50"
                title="Copy answer"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-green-500" />
                    <span className="text-green-500">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>

              {hasSources && (
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-blue-600 transition-colors px-2 py-1 rounded-md hover:bg-blue-50 ml-auto"
                >
                  <FileText className="h-3.5 w-3.5" />
                  <span>
                    {sourceEntries.length} Source{sourceEntries.length !== 1 ? "s" : ""}
                  </span>
                  {showSources ? (
                    <ChevronUp className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5" />
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Sources Panel */}
          {hasSources && showSources && (
            <div className="mt-2 bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2 animate-in slide-in-from-top-2">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
                Sources
              </div>
              {sourceEntries.map(([url, title], idx) => (
                <a
                  key={idx}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 p-2 rounded-lg hover:bg-white hover:shadow-sm transition-all group"
                >
                  <div className="h-6 w-6 rounded bg-blue-100 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-blue-700">{idx + 1}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700 group-hover:text-blue-700 transition-colors truncate font-medium">
                      {title}
                    </p>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5">{url}</p>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-500 transition-colors shrink-0 mt-1" />
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
