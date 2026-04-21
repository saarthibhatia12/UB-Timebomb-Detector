import { Upload, Zap, RotateCcw, AlertTriangle } from 'lucide-react';
import { useRef } from 'react';

const SAMPLE_CODE = `// Classic UB Time Bomb: signed integer overflow
// The optimizer assumes x + 1 > x is ALWAYS true
// (because signed overflow is undefined behavior).
// At -O2, the comparison is eliminated entirely.
#include <limits.h>

int always_greater(int x) {
    return x + 1 > x;   // UB when x == INT_MAX
}`;

export default function Header({ sourceCode, onSourceChange, onAnalyze, loading, error, onReset }) {
  const fileInputRef = useRef(null);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      onSourceChange(ev.target.result);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleLoadSample = () => {
    onSourceChange(SAMPLE_CODE);
  };

  return (
    <header className="relative overflow-hidden">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-r from-dark-950 via-dark-900 to-dark-950" />
      <div className="absolute inset-0 bg-gradient-to-b from-accent-red/5 via-transparent to-transparent" />

      <div className="relative z-10 px-6 py-5">
        {/* Title row */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-accent-red/15 border border-accent-red/20">
              <AlertTriangle className="w-5 h-5 text-accent-red" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">
                UB Time Bomb Detector
              </h1>
              <p className="text-xs text-gray-400 font-medium tracking-wide">
                Static undefined behavior analyzer for C/C++ · LLVM IR differential analysis
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleLoadSample}
              className="px-3 py-2 text-xs font-medium text-gray-300 bg-dark-700/60 hover:bg-dark-600/80 border border-dark-500/40 rounded-lg transition-all duration-200 hover:text-white cursor-pointer"
            >
              Load Sample
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".c,.h,.cpp,.cc"
              className="hidden"
              onChange={handleFileUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-300 bg-dark-700/60 hover:bg-dark-600/80 border border-dark-500/40 rounded-lg transition-all duration-200 hover:text-white cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" />
              Upload .c
            </button>

            {onReset && (
              <button
                onClick={onReset}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-400 hover:text-white bg-dark-700/40 hover:bg-dark-600/60 border border-dark-500/30 rounded-lg transition-all duration-200 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset
              </button>
            )}

            <button
              onClick={onAnalyze}
              disabled={loading || !sourceCode?.trim()}
              className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-gradient-to-r from-accent-red to-accent-orange hover:from-accent-red/90 hover:to-accent-orange/90 rounded-lg transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-accent-red/20 hover:shadow-accent-red/30 cursor-pointer"
            >
              {loading ? (
                <>
                  <div className="spinner" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Analyze
                </>
              )}
            </button>
          </div>
        </div>

        {/* Source code editor */}
        <div className="relative">
          <textarea
            value={sourceCode}
            onChange={(e) => onSourceChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                onAnalyze();
              }
            }}
            placeholder="// Paste your C code here, or upload a .c file...&#10;// Press Ctrl+Enter to analyze"
            className="w-full h-40 p-4 font-mono text-sm text-gray-200 bg-dark-900/80 border border-dark-600/50 rounded-xl resize-none focus:outline-none focus:border-accent-blue/40 focus:ring-1 focus:ring-accent-blue/20 transition-all duration-200 placeholder:text-gray-600"
            spellCheck={false}
          />
          <div className="absolute bottom-3 right-3 text-[10px] text-gray-600 font-mono">
            Ctrl+Enter to analyze
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-3 px-4 py-2.5 bg-accent-red/10 border border-accent-red/20 rounded-lg text-sm text-accent-red animate-fade-in">
            <span className="font-semibold">Error:</span> {error}
          </div>
        )}
      </div>
    </header>
  );
}
