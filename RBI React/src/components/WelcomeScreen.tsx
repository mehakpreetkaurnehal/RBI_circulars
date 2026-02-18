import { BookOpen, Shield, CreditCard, FileSearch, Landmark } from "lucide-react";

interface WelcomeScreenProps {
  onSuggestionClick: (query: string) => void;
  serverInfo?: string;
}

const suggestions = [
  {
    icon: Shield,
    label: "KYC Guidelines",
    query: "What are the latest RBI KYC guidelines for banks?",
    color: "from-blue-500 to-blue-600",
  },
  {
    icon: BookOpen,
    label: "NPA Classification",
    query: "How are NPAs classified under RBI norms?",
    color: "from-amber-500 to-orange-600",
  },
  {
    icon: CreditCard,
    label: "Digital Payments",
    query: "What are RBI's guidelines on UPI and digital payments?",
    color: "from-emerald-500 to-teal-600",
  },
  {
    icon: FileSearch,
    label: "Lending Norms",
    query: "What are the digital lending guidelines issued by RBI?",
    color: "from-purple-500 to-violet-600",
  },
];

export function WelcomeScreen({ onSuggestionClick, serverInfo }: WelcomeScreenProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full space-y-8">
        {/* Logo & Title */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 shadow-xl shadow-blue-200 mx-auto">
            <Landmark className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
              RBI Circular QA Assistant
            </h1>
            <p className="text-slate-500 mt-2 text-base">
              Ask questions about RBI circulars, guidelines, and regulations.
              <br />
              Powered by hybrid RAG retrieval on your RBI circular database.
            </p>
          </div>
        </div>

        {/* Feature Pills */}
        <div className="flex flex-wrap justify-center gap-2">
          {["FAISS Semantic Search", "BM25 Keyword Search", "Cross-Encoder Reranking", "Gemini LLM", "Follow-up Questions"].map(
            (feature) => (
              <span
                key={feature}
                className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200"
              >
                {feature}
              </span>
            )
          )}
        </div>

        {/* Server Info */}
        {serverInfo && (
          <div className="text-center">
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Connected — {serverInfo}
            </span>
          </div>
        )}

        {/* Suggestion Cards */}
        <div>
          <p className="text-sm font-medium text-slate-500 mb-3 text-center">
            Try asking about:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {suggestions.map((s) => (
              <button
                key={s.label}
                onClick={() => onSuggestionClick(s.query)}
                className="flex items-start gap-3 p-4 rounded-xl border border-slate-200 bg-white hover:border-blue-300 hover:shadow-md hover:shadow-blue-50 transition-all text-left group active:scale-[0.98]"
              >
                <div
                  className={`h-9 w-9 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center shrink-0 shadow-sm`}
                >
                  <s.icon className="h-4 w-4 text-white" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-800 group-hover:text-blue-700 transition-colors">
                    {s.label}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{s.query}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Info */}
        <div className="text-center">
          <p className="text-xs text-slate-400 bg-slate-50 inline-block px-4 py-2 rounded-full border border-slate-100">
            📚 Answers are generated exclusively from your RBI circular database — no internet data.
          </p>
        </div>
      </div>
    </div>
  );
}
