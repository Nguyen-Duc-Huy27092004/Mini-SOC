import { useState, useCallback } from 'react';
import {
  Brain, AlertTriangle, CheckCircle2, XCircle, ChevronDown, ChevronUp,
  Shield, Crosshair, Zap, ExternalLink, Loader2, RefreshCw, Info
} from 'lucide-react';
import api from '../../../shared/api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface RecommendedAction {
  action: string;
  priority: number;
  reason: string;
}

export interface AIAnalysis {
  threat_classification: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'FALSE_POSITIVE';
  confidence: number;
  summary: string;
  attack_narrative: string;
  iocs: string[];
  mitre_techniques: string[];
  recommended_actions: RecommendedAction[];
  false_positive_indicators: string[];
  additional_context: string;
  simulation_mode?: boolean;
}

interface AiAnalysisPanelProps {
  alertId?: string;
  alertData?: Record<string, unknown>;
  /** If provided, the analysis is pre-loaded — no fetch needed */
  preloadedAnalysis?: AIAnalysis;
  className?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const CLASSIFICATION_STYLES: Record<string, { bg: string; border: string; text: string; icon: React.FC<{ className?: string }> }> = {
  CRITICAL:       { bg: 'bg-red-500/10',     border: 'border-red-500/40',    text: 'text-red-400',     icon: AlertTriangle },
  HIGH:           { bg: 'bg-orange-500/10',  border: 'border-orange-500/40', text: 'text-orange-400',  icon: AlertTriangle },
  MEDIUM:         { bg: 'bg-amber-500/10',   border: 'border-amber-500/40',  text: 'text-amber-400',   icon: Info },
  LOW:            { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40',text: 'text-emerald-400', icon: CheckCircle2 },
  FALSE_POSITIVE: { bg: 'bg-slate-500/10',   border: 'border-slate-500/40',  text: 'text-slate-400',   icon: XCircle },
};

const ACTION_ICONS: Record<string, string> = {
  firewall_block:      '🛡️',
  notify_slack:        '💬',
  notify_telegram:     '📱',
  isolate_host:        '🔒',
  kill_process:        '⚡',
  escalate_incident:   '⬆️',
  log:                 '📋',
  webhook:             '🔗',
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 85 ? '#f87171' : pct >= 60 ? '#fb923c' : '#34d399';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono text-slate-300 w-10 text-right">{pct}%</span>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function AiAnalysisPanel({ alertId, alertData, preloadedAnalysis, className = '' }: AiAnalysisPanelProps) {
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(preloadedAnalysis ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [showNarrative, setShowNarrative] = useState(false);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = alertId ? { alert_id: alertId } : { alert_data: alertData ?? {} };
      const res = await api.post('/ai/analyze-alert', body);
      setAnalysis(res.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail ?? (err as { message?: string })?.message ?? 'Unknown error';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [alertId, alertData]);

  const styles = analysis ? (CLASSIFICATION_STYLES[analysis.threat_classification] ?? CLASSIFICATION_STYLES.MEDIUM) : null;
  const ClassIcon = styles?.icon ?? Brain;

  return (
    <div className={`rounded-xl border bg-slate-900/80 overflow-hidden ${className}`} style={{ borderColor: styles ? undefined : '#334155' }}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/40 transition"
      >
        <div className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${styles ? `${styles.bg} border ${styles.border}` : 'bg-violet-500/10 border border-violet-500/30'}`}>
            <Brain className={`w-3.5 h-3.5 ${styles ? styles.text : 'text-violet-400'}`} />
          </div>
          <span className="text-sm font-semibold text-white">AI Security Analyst</span>
          {analysis?.simulation_mode && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 font-medium">SIM</span>
          )}
          {analysis && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${styles?.bg} ${styles?.border} ${styles?.text}`}>
              {analysis.threat_classification}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!analysis && !loading && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); runAnalysis(); }}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition"
            >
              Phân tích
            </button>
          )}
          {analysis && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); runAnalysis(); }}
              title="Chạy lại phân tích"
              className="text-slate-500 hover:text-slate-300 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </div>
      </button>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-800/60">
          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center gap-3 py-8">
              <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
              <p className="text-xs text-slate-400">Đang phân tích với Gemini AI…</p>
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
              ⚠️ {error}
            </div>
          )}

          {/* Empty state */}
          {!analysis && !loading && !error && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                <Brain className="w-6 h-6 text-violet-400 opacity-60" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-300">Chưa có phân tích AI</p>
                <p className="text-xs text-slate-500 mt-1">Nhấn "Phân tích" để Gemini AI đánh giá alert này</p>
              </div>
            </div>
          )}

          {/* Analysis result */}
          {analysis && !loading && (
            <>
              {/* Classification + Confidence */}
              <div className={`mt-3 p-3 rounded-xl border ${styles?.bg} ${styles?.border}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <ClassIcon className={`w-4 h-4 ${styles?.text}`} />
                    <span className={`text-sm font-bold ${styles?.text}`}>{analysis.threat_classification}</span>
                  </div>
                </div>
                <ConfidenceBar value={analysis.confidence} />
                <p className="text-xs text-slate-300 mt-2 leading-relaxed">{analysis.summary}</p>
              </div>

              {/* Narrative (expandable) */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowNarrative(v => !v)}
                  className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition font-medium"
                >
                  <Shield className="w-3.5 h-3.5" />
                  {showNarrative ? 'Ẩn chi tiết phân tích' : 'Xem chi tiết phân tích'}
                  {showNarrative ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                {showNarrative && (
                  <p className="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-800/40 rounded-lg p-3">
                    {analysis.attack_narrative}
                  </p>
                )}
              </div>

              {/* MITRE ATT&CK */}
              {analysis.mitre_techniques.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Crosshair className="w-3.5 h-3.5 text-rose-400" /> MITRE ATT&CK
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.mitre_techniques.map(t => (
                      <a
                        key={t}
                        href={`https://attack.mitre.org/techniques/${t.replace('.', '/')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-rose-500/10 border border-rose-500/20 text-rose-300 hover:bg-rose-500/20 transition"
                      >
                        {t} <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* IOCs */}
              {analysis.iocs.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">🔎 IOCs</p>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.iocs.map(ioc => (
                      <span key={ioc} className="px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300">
                        {ioc}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Actions */}
              {analysis.recommended_actions.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-cyan-400" /> Hành động đề xuất
                  </p>
                  <div className="space-y-1.5">
                    {[...analysis.recommended_actions]
                      .sort((a, b) => a.priority - b.priority)
                      .map((act, i) => (
                        <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/50">
                          <span className="text-sm leading-none mt-0.5">{ACTION_ICONS[act.action] ?? '⚙️'}</span>
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-slate-200 font-mono">{act.action}</p>
                            <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{act.reason}</p>
                          </div>
                          <span className="ml-auto shrink-0 text-[10px] font-bold text-slate-500">#{act.priority}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* False Positive Indicators */}
              {analysis.false_positive_indicators.length > 0 && (
                <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/40">
                  <p className="text-[11px] font-semibold text-slate-400 mb-1.5">⚠️ Dấu hiệu False Positive</p>
                  <ul className="space-y-1">
                    {analysis.false_positive_indicators.map((fp, i) => (
                      <li key={i} className="text-[11px] text-slate-500 flex gap-1.5">
                        <span className="shrink-0">•</span>{fp}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
