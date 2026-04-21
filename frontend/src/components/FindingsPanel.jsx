import { ChevronRight, MapPin } from 'lucide-react';

const SEVERITY_CONFIG = {
  critical: { label: 'CRIT', bg: 'bg-accent-red/15', text: 'text-accent-red', border: 'border-accent-red/30' },
  high: { label: 'HIGH', bg: 'bg-accent-orange/15', text: 'text-accent-orange', border: 'border-accent-orange/30' },
  medium: { label: 'MED', bg: 'bg-accent-yellow/15', text: 'text-accent-yellow', border: 'border-accent-yellow/30' },
  low: { label: 'LOW', bg: 'bg-accent-green/15', text: 'text-accent-green', border: 'border-accent-green/30' },
  info: { label: 'INFO', bg: 'bg-accent-blue/15', text: 'text-accent-blue', border: 'border-accent-blue/30' },
};

const CATEGORY_LABELS = {
  signed_overflow: 'Signed Overflow',
  null_deref: 'Null Deref',
  strict_aliasing: 'Strict Aliasing',
  uninitialized_use: 'Uninitialized',
  unknown: 'Unknown UB',
  inlined: 'Inlined',
};

function SeverityBadge({ severity }) {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.medium;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${config.bg} ${config.text} border ${config.border}`}>
      {config.label}
    </span>
  );
}

function ConfidenceBadge({ confidence }) {
  const colors = {
    HIGH: 'text-accent-green bg-accent-green/10',
    MEDIUM: 'text-accent-yellow bg-accent-yellow/10',
    PARTIAL: 'text-accent-orange bg-accent-orange/10',
    LOW: 'text-gray-400 bg-gray-500/10',
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase ${colors[confidence] || colors.LOW}`}>
      {confidence}
    </span>
  );
}

export default function FindingsPanel({ findings, selectedFinding, onSelectFinding }) {
  if (!findings || findings.length === 0) {
    return (
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Findings</h3>
        <div className="flex flex-col items-center py-8 text-gray-500">
          <span className="text-4xl mb-3">✅</span>
          <p className="text-sm font-medium">No UB time bombs detected</p>
          <p className="text-xs text-gray-600 mt-1">Code appears safe at this analysis level</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Findings
        </h3>
        <span className="text-xs font-mono text-gray-500">{findings.length} issue{findings.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="overflow-auto max-h-[400px] divide-y divide-white/[0.04]">
        {findings.map((finding, i) => {
          const isSelected = selectedFinding === finding;
          const categoryLabel = CATEGORY_LABELS[finding.category] || finding.category;

          return (
            <button
              key={i}
              onClick={() => onSelectFinding(finding)}
              className={`w-full text-left px-4 py-3 flex items-start gap-3 transition-all duration-150 cursor-pointer group ${
                isSelected
                  ? 'bg-white/[0.06] border-l-2 border-accent-blue'
                  : 'hover:bg-white/[0.03] border-l-2 border-transparent'
              }`}
            >
              <div className="pt-0.5 shrink-0">
                <SeverityBadge severity={finding.severity} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-sm font-semibold text-gray-200 truncate">
                    {finding.readable_name}
                  </span>
                  <ConfidenceBadge confidence={finding.confidence} />
                </div>
                <p className="text-xs text-gray-400 truncate">
                  {categoryLabel}
                </p>
                {finding.location?.line && (
                  <div className="flex items-center gap-1 mt-1 text-[11px] text-gray-500">
                    <MapPin className="w-3 h-3" />
                    Line {finding.location.line}
                  </div>
                )}
              </div>

              <ChevronRight className={`w-4 h-4 mt-1 shrink-0 transition-transform duration-150 ${
                isSelected ? 'text-accent-blue translate-x-0' : 'text-gray-600 -translate-x-1 group-hover:translate-x-0'
              }`} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
