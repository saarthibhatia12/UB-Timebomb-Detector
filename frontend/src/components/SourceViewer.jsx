import { useRef, useEffect } from 'react';

export default function SourceViewer({ sourceLines, findings, selectedFinding }) {
  const containerRef = useRef(null);

  // Get set of flagged line numbers
  const flaggedLines = new Map();
  if (findings) {
    for (const f of findings) {
      if (f.location?.line) {
        const severity = f.severity;
        flaggedLines.set(f.location.line, severity);
      }
    }
  }

  // Selected line
  const selectedLine = selectedFinding?.location?.line;

  // Scroll to selected line
  useEffect(() => {
    if (selectedLine && containerRef.current) {
      const lineEl = containerRef.current.querySelector(`[data-line="${selectedLine}"]`);
      if (lineEl) {
        lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [selectedLine]);

  if (!sourceLines || sourceLines.length === 0) {
    return (
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Source Code</h3>
        <p className="text-gray-500 text-sm">No source code to display.</p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Source Code
        </h3>
      </div>
      <div ref={containerRef} className="overflow-auto max-h-[400px] font-mono text-[13px]">
        {sourceLines.map((line, i) => {
          const lineNum = i + 1;
          const severity = flaggedLines.get(lineNum);
          const isSelected = lineNum === selectedLine;
          const isFlagged = !!severity;

          let lineClass = 'flex hover:bg-white/[0.02] transition-colors duration-100';
          if (isSelected) {
            lineClass += severity === 'critical'
              ? ' line-highlight-critical bg-accent-red/10'
              : ' line-highlight-high bg-accent-orange/8';
          } else if (isFlagged) {
            lineClass += severity === 'critical'
              ? ' line-highlight-critical'
              : ' line-highlight-high';
          }

          return (
            <div key={lineNum} data-line={lineNum} className={lineClass}>
              <span className="inline-block w-12 text-right pr-3 py-px text-gray-600 select-none shrink-0 text-xs leading-6">
                {lineNum}
              </span>
              <span className={`flex-1 py-px pr-4 leading-6 whitespace-pre ${isFlagged ? 'text-gray-100' : 'text-gray-300'}`}>
                {line || '\u00A0'}
              </span>
              {isFlagged && (
                <span className="shrink-0 pr-3 py-px">
                  <span className={`inline-block w-2 h-2 rounded-full mt-2 ${severity === 'critical' ? 'bg-accent-red animate-pulse-glow' : 'bg-accent-orange'}`} />
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
