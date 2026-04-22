import { useCallback, useEffect, useState } from 'react';

export function buildFindingKey(finding) {
  if (!finding) {
    return '';
  }

  const locationFile = finding.location?.file || 'input';
  const locationLine = finding.location?.line || 0;

  return [
    finding.readable_name || '',
    finding.category || '',
    `${locationFile}:${locationLine}`,
    finding.metrics?.blocks_O0 ?? '',
    finding.metrics?.blocks_O2 ?? '',
    finding.metrics?.branches_O0 ?? '',
    finding.metrics?.branches_O2 ?? '',
  ].join('|');
}

export function useAIExplain() {
  const [explanationsByKey, setExplanationsByKey] = useState({});
  const [errorsByKey, setErrorsByKey] = useState({});
  const [loadingKey, setLoadingKey] = useState(null);
  const [aiExplainStatus, setAIExplainStatus] = useState({
    loading: true,
    enabled: false,
    model: '',
    fallback_model: '',
    max_chars: 0,
    reason: 'Checking AI configuration...',
    error: '',
  });

  useEffect(() => {
    let cancelled = false;

    const loadStatus = async () => {
      try {
        const response = await fetch('/api/ai-explain/status');
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || 'Unable to determine AI availability');
        }

        const data = await response.json();
        if (cancelled) return;

        setAIExplainStatus({
          loading: false,
          enabled: Boolean(data.enabled),
          model: data.model || '',
          fallback_model: data.fallback_model || '',
          max_chars: data.max_chars || 0,
          reason: data.reason || '',
          error: '',
        });
      } catch (error) {
        if (cancelled) return;

        const message = error instanceof Error ? error.message : 'Unable to determine AI availability';
        setAIExplainStatus({
          loading: false,
          enabled: false,
          model: '',
          fallback_model: '',
          max_chars: 0,
          reason: 'AI explanations are unavailable right now.',
          error: message,
        });
      }
    };

    loadStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  const explainFinding = useCallback(async (finding) => {
    const findingKey = buildFindingKey(finding);
    if (!findingKey) {
      throw new Error('Cannot generate explanation without a selected finding');
    }

    if (!aiExplainStatus.enabled) {
      throw new Error(aiExplainStatus.reason || 'AI not configured. Set GROQ_API_KEY.');
    }

    if (explanationsByKey[findingKey]) {
      return explanationsByKey[findingKey];
    }

    setLoadingKey(findingKey);
    setErrorsByKey((prev) => ({ ...prev, [findingKey]: '' }));

    try {
      const response = await fetch('/api/ai-explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          finding,
          source_snippet: finding?.source_snippet || null,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to generate AI explanation');
      }

      const data = await response.json();
      setExplanationsByKey((prev) => ({
        ...prev,
        [findingKey]: data,
      }));
      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to generate AI explanation';
      setErrorsByKey((prev) => ({ ...prev, [findingKey]: message }));
      throw error;
    } finally {
      setLoadingKey((current) => (current === findingKey ? null : current));
    }
  }, [aiExplainStatus.enabled, aiExplainStatus.reason, explanationsByKey]);

  const resetAIExplain = useCallback(() => {
    setExplanationsByKey({});
    setErrorsByKey({});
    setLoadingKey(null);
  }, []);

  return {
    explanationsByKey,
    errorsByKey,
    loadingKey,
    aiExplainStatus,
    explainFinding,
    resetAIExplain,
  };
}
