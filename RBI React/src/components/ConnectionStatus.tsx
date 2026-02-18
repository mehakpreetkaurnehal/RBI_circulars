import { WifiOff, RefreshCw, Server, Terminal } from "lucide-react";

interface ConnectionStatusProps {
  isConnected: boolean | null;
  error: string | null;
  onRetry: () => void;
}

export function ConnectionStatus({ isConnected, error, onRetry }: ConnectionStatusProps) {
  // Still checking
  if (isConnected === null) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-slate-100 mx-auto">
            <Server className="h-8 w-8 text-slate-400 animate-pulse" />
          </div>
          <h2 className="text-xl font-semibold text-slate-700">Connecting to backend...</h2>
          <p className="text-slate-400 text-sm">Trying to reach the FastAPI server at localhost:8000</p>
        </div>
      </div>
    );
  }

  // Disconnected
  if (!isConnected) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="max-w-lg w-full text-center space-y-6">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-red-50 mx-auto">
            <WifiOff className="h-8 w-8 text-red-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Backend Not Connected</h2>
            <p className="text-slate-500 text-sm mt-2">
              The React frontend needs the FastAPI backend server running to work.
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-left">
              <p className="text-xs font-mono text-red-600 break-all">{error}</p>
            </div>
          )}

          {/* Setup instructions */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 text-left space-y-4">
            <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              Setup Instructions
            </h3>

            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">1. Install Python dependencies:</p>
                <code className="block bg-slate-900 text-green-400 text-xs p-3 rounded-lg font-mono">
                  pip install fastapi uvicorn google-genai faiss-cpu sentence-transformers rank_bm25 python-dotenv
                </code>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">2. Save <code className="bg-slate-200 px-1 rounded">backend_api.py</code> in your project directory (alongside rbi_scrape_text_fixed/)</p>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">3. Create <code className="bg-slate-200 px-1 rounded">.env</code> with your Gemini key:</p>
                <code className="block bg-slate-900 text-green-400 text-xs p-3 rounded-lg font-mono">
                  GEMINI_API_KEY=your_key_here
                </code>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">4. Run the backend:</p>
                <code className="block bg-slate-900 text-green-400 text-xs p-3 rounded-lg font-mono">
                  uvicorn backend_api:app --host 0.0.0.0 --port 8000 --reload
                </code>
              </div>
            </div>
          </div>

          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium text-sm shadow-md shadow-blue-200 active:scale-[0.98]"
          >
            <RefreshCw className="h-4 w-4" />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return null;
}
