import { Download, Wrench, Info, BarChart3, Sparkles, Loader2 } from 'lucide-react';

export default function ReportPanel({
  finding,
  report,
  aiExplain,
  aiExplainLoading = false,
  aiExplainError = '',
  aiExplainStatus = { loading: false, enabled: false, reason: '' },
  onRequestAIExplain,
}) {
  if (!finding) {
    return (
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Details</h3>
        <p className="text-gray-500 text-sm">Select a finding to see details and fix suggestions.</p>
      </div>
    );
  }

  const metrics = finding.metrics || {};
  const aiDetails = aiExplain?.explanation || null;
  const aiConfigReady = Boolean(aiExplainStatus?.enabled);
  const aiConfigLoading = Boolean(aiExplainStatus?.loading);
  const aiConfigReason = aiExplainStatus?.reason || '';

  const handleExport = () => {
    if (!report) return;

    const lines = [];
    lines.push('='.repeat(60));
    lines.push('  UB TIME BOMB DETECTOR — ANALYSIS REPORT');
    lines.push('='.repeat(60));
    lines.push(`  File: ${report.source_file}`);
    lines.push(`  Risk Score: ${report.risk_score}/100 (${report.risk_level})`);
    lines.push(`  Functions Analyzed: ${report.functions_analyzed}`);
    lines.push(`  Time Bombs Found: ${report.total_findings}`);
    lines.push('='.repeat(60));

    for (const [i, f] of report.findings.entries()) {
      lines.push('');
      lines.push(`[${f.severity_icon} ${f.severity.toUpperCase()}] #${i + 1} — ${f.readable_name}`);
      lines.push(`  Category  : ${f.category}`);
      lines.push(`  Confidence: ${f.confidence}`);
      if (f.location) {
        lines.push(`  Location  : ${f.location.file || '?'}:${f.location.line || '?'}`);
      }
      lines.push(`  Detail    : ${f.detail}`);
      lines.push(`  Fix       : ${f.fix}`);
      if (f.source_snippet) {
        lines.push('  Code:');
        for (const sl of f.source_snippet.split('\n')) {
          lines.push(`    ${sl}`);
        }
      }
    }

    const text = lines.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ub_report.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRequestExplain = () => {
    if (!onRequestAIExplain || aiExplainLoading) {
      return;
    }
    onRequestAIExplain(finding);
  };

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Details
        </h3>
        {report && (
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-gray-400 hover:text-white bg-dark-700/50 hover:bg-dark-600/70 border border-dark-500/30 rounded-md transition-all cursor-pointer"
          >
            <Download className="w-3 h-3" />
            Export
          </button>
        )}
      </div>

      <div className="p-4 space-y-4 max-h-[400px] overflow-auto">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Info className="w-3.5 h-3.5 text-accent-blue" />
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Analysis</span>
          </div>
          <p className="text-sm text-gray-300 leading-relaxed pl-5">
            {finding.detail}
          </p>
        </div>

        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Wrench className="w-3.5 h-3.5 text-accent-green" />
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Fix Suggestion</span>
          </div>
          <div className="pl-5 p-3 bg-accent-green/5 border border-accent-green/10 rounded-lg">
            <p className="text-sm text-accent-green/90 leading-relaxed">
              {finding.fix}
            </p>
          </div>
        </div>

        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Sparkles className="w-3.5 h-3.5 text-accent-blue" />
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">AI Explanation</span>
          </div>
          <div className="pl-5 space-y-2">
            <p className="text-[11px] text-gray-500">This sends code and IR excerpts to Groq.</p>
            {!aiConfigLoading && !aiConfigReady && aiConfigReason && (
              <p className="text-[11px] text-accent-orange">{aiConfigReason}</p>
            )}
            <button
              onClick={handleRequestExplain}
              disabled={aiExplainLoading || aiConfigLoading || !aiConfigReady}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-gray-300 hover:text-white bg-dark-700/50 hover:bg-dark-600/70 border border-dark-500/40 rounded-md transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {aiExplainLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              {aiConfigLoading
                ? 'Checking AI Configuration...'
                : !aiConfigReady
                  ? 'AI Disabled'
                  : aiDetails
                    ? 'Explanation Ready'
                    : 'Generate AI Explanation'}
            </button>

            {aiConfigLoading && (
              <p className="text-xs text-gray-500">Checking whether Groq is configured locally...</p>
            )}

            {aiExplainLoading && (
              <p className="text-xs text-gray-500">Generating AI explanation for this finding...</p>
            )}

            {aiExplainError && aiConfigReady && (
              <p className="text-xs text-accent-orange">{aiExplainError}</p>
            )}

            {aiDetails && aiConfigReady && (
              <div className="space-y-2 p-3 bg-accent-blue/5 border border-accent-blue/15 rounded-lg">
                {aiExplain?.model && (
                  <p className="text-[11px] font-mono text-gray-500">Model: {aiExplain.model}</p>
                )}
                <ExplanationRow label="Summary" value={aiDetails.summary_plain} />
                <ExplanationRow label="What is the UB" value={aiDetails.what_is_the_ub} />
                <ExplanationRow label="IR change" value={aiDetails.what_changed_in_ir} />
                <ExplanationRow label="Why optimizer changed code" value={aiDetails.why_optimizer_removed_code} />
                <ExplanationRow
                  label="Suggested fixes"
                  value={Array.isArray(aiDetails.fixes) ? aiDetails.fixes.join(' | ') : ''}
                />
                <ExplanationRow label="Safer rewrite" value={aiDetails.safer_rewrite} />
                <ExplanationRow label="Caveats" value={aiDetails.caveats} />
              </div>
            )}

            {!aiConfigLoading && !aiConfigReady && !aiDetails && (
              <p className="text-xs text-gray-500">AI explanations are disabled until GROQ_API_KEY is set.</p>
            )}

            {!aiDetails && !aiExplainLoading && !aiExplainError && aiConfigReady && (
              <p className="text-xs text-gray-500">No AI explanation generated yet for this selected finding.</p>
            )}
          </div>
        </div>

        {metrics.blocks_O0 !== undefined && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <BarChart3 className="w-3.5 h-3.5 text-accent-purple" />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">IR Metrics</span>
            </div>
            <div className="pl-5 grid grid-cols-2 gap-2">
              <MetricRow label="Basic Blocks" o0={metrics.blocks_O0} o2={metrics.blocks_O2} />
              <MetricRow label="Branches" o0={metrics.branches_O0} o2={metrics.branches_O2} />
              {metrics.null_checks_O0 > 0 && (
                <MetricRow label="Null Checks" o0={metrics.null_checks_O0} o2={metrics.null_checks_O2} />
              )}
            </div>
            <div className="pl-5 mt-2 flex flex-wrap gap-2">
              {metrics.nsw_added && <Tag label="nsw added" color="red" />}
              {metrics.undef_exposed && <Tag label="undef exposed" color="orange" />}
              {metrics.signed_overflow_folded && <Tag label="overflow folded" color="red" />}
              {metrics.loop_overflow_guard && <Tag label="loop guard removed" color="red" />}
              {metrics.type_punning && <Tag label="type punning" color="orange" />}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ExplanationRow({ label, value }) {
  if (!value) {
    return null;
  }

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">{label}</p>
      <p className="text-sm text-gray-300 leading-relaxed">{value}</p>
    </div>
  );
}

function MetricRow({ label, o0, o2 }) {
  const changed = o0 !== o2 && o0 >= 0;
  return (
    <div className="flex items-center justify-between px-3 py-1.5 bg-dark-800/50 rounded-md text-xs">
      <span className="text-gray-400">{label}</span>
      <div className="flex items-center gap-1.5 font-mono">
        <span className="text-gray-300">{o0}</span>
        <span className="text-gray-600">→</span>
        <span className={changed ? 'text-accent-red font-bold' : 'text-gray-300'}>{o2}</span>
      </div>
    </div>
  );
}

function Tag({ label, color }) {
  const colors = {
    red: 'bg-accent-red/10 text-accent-red border-accent-red/20',
    orange: 'bg-accent-orange/10 text-accent-orange border-accent-orange/20',
    yellow: 'bg-accent-yellow/10 text-accent-yellow border-accent-yellow/20',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${colors[color] || colors.yellow}`}>
      {label}
    </span>
  );
}
