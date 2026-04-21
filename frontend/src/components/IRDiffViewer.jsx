import { DiffEditor } from '@monaco-editor/react';

export default function IRDiffViewer({ o0IR, o2IR }) {
  if (!o0IR && !o2IR) {
    return (
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">IR Diff</h3>
        <p className="text-gray-500 text-sm">Select a finding to view the LLVM IR difference.</p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          LLVM IR Diff
        </h3>
        <div className="flex gap-4 text-[11px] font-medium">
          <span className="text-accent-green">← O0 (Unoptimized)</span>
          <span className="text-accent-red">O2 (Optimized) →</span>
        </div>
      </div>
      <div className="h-[350px]">
        <DiffEditor
          original={o0IR || ''}
          modified={o2IR || ''}
          language="llvm"
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            renderSideBySide: true,
            wordWrap: 'on',
            overviewRulerBorder: false,
            scrollbar: {
              verticalScrollbarSize: 6,
              horizontalScrollbarSize: 6,
            },
          }}
        />
      </div>
    </div>
  );
}
