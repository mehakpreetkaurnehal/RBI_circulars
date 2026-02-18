import { Bot } from "lucide-react";

export function LoadingIndicator() {
  return (
    <div className="flex gap-3 py-2">
      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shrink-0 mt-1 shadow-sm">
        <Bot className="h-4 w-4 text-white" />
      </div>
      <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="h-2 w-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0ms]" />
            <div className="h-2 w-2 rounded-full bg-blue-400 animate-bounce [animation-delay:150ms]" />
            <div className="h-2 w-2 rounded-full bg-blue-400 animate-bounce [animation-delay:300ms]" />
          </div>
          <span className="text-sm text-slate-400">Searching RBI circular database & generating answer...</span>
        </div>
      </div>
    </div>
  );
}
