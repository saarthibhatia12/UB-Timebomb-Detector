import { useState } from 'react';
import { useAnalysis } from './hooks/useAnalysis';
import Header from './components/Header';
import StatsBar from './components/StatsBar';
import SourceViewer from './components/SourceViewer';
import IRDiffViewer from './components/IRDiffViewer';
import FindingsPanel from './components/FindingsPanel';
import ReportPanel from './components/ReportPanel';
import CVEDatabase from './components/CVEDatabase';

function App() {
  const { report, loading, error, analyze, reset } = useAnalysis();
  const [sourceCode, setSourceCode] = useState('');
  const [selectedFinding, setSelectedFinding] = useState(null);

  const handleAnalyze = async () => {
    if (!sourceCode.trim()) return;
    try {
      const result = await analyze(sourceCode);
      if (result.findings.length > 0) {
        setSelectedFinding(result.findings[0]);
      } else {
        setSelectedFinding(null);
      }
    } catch (e) {
      // Error handled by hook
    }
  };

  const handleReset = () => {
    reset();
    setSourceCode('');
    setSelectedFinding(null);
  };

  const handleLoadCVE = (code) => {
    setSourceCode(code);
    // Auto-scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-dark-950 text-gray-100">
      <Header
        sourceCode={sourceCode}
        onSourceChange={setSourceCode}
        onAnalyze={handleAnalyze}
        loading={loading}
        error={error}
        onReset={report ? handleReset : null}
      />

      {report && (
        <div className="animate-fade-in">
          <StatsBar report={report} />

          <main className="grid grid-cols-1 lg:grid-cols-2 gap-4 px-6 pb-4">
            <div className="space-y-4">
              <SourceViewer
                sourceLines={report.source_lines}
                findings={report.findings}
                selectedFinding={selectedFinding}
              />
              <IRDiffViewer
                o0IR={selectedFinding?.ir?.O0 || ''}
                o2IR={selectedFinding?.ir?.O2 || ''}
              />
            </div>

            <div className="space-y-4">
              <FindingsPanel
                findings={report.findings}
                selectedFinding={selectedFinding}
                onSelectFinding={setSelectedFinding}
              />
              <ReportPanel finding={selectedFinding} report={report} />
            </div>
          </main>
        </div>
      )}

      {/* CVE cards always visible at bottom */}
      <CVEDatabase onLoadCase={handleLoadCVE} />

      {/* Footer */}
      <footer className="px-6 py-4 border-t border-white/5 text-center">
        <p className="text-xs text-gray-600">
          UB Time Bomb Detector · Differential LLVM IR analysis · Built with FastAPI + React
        </p>
      </footer>
    </div>
  );
}

export default App;
