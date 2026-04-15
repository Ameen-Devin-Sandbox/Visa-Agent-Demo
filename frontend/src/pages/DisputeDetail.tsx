import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Clock, Scale, FileText, ShieldCheck, ShieldX,
  AlertTriangle, ChevronRight, CheckCircle2, XCircle, Send,
} from 'lucide-react';
import { api } from '../lib/api';
import type { DisputeDetail as DisputeDetailType, EvidenceInput } from '../lib/types';
import { CATEGORIES, STAGES, ENVIRONMENTS } from '../lib/types';
import { StageBadge, ResolutionBadge, ConfidenceMeter } from '../components/Badges';

function formatAgent(agent: string | null | undefined): string {
  if (!agent) return '--';
  return agent
    .replace(/_agent$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const EMPTY_EVIDENCE: EvidenceInput = {
  description: '',
  evidence_type: '',
  provided_by: 'issuer',
  is_compelling_evidence: false,
};

export default function DisputeDetail() {
  const { id } = useParams<{ id: string }>();

  const [dispute, setDispute] = useState<DisputeDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Rule evaluations collapsible
  const [rulesOpen, setRulesOpen] = useState(false);

  // Add evidence form
  const [showEvidenceForm, setShowEvidenceForm] = useState(false);
  const [evidenceForm, setEvidenceForm] = useState<EvidenceInput>({ ...EMPTY_EVIDENCE });
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  // Human review
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Escalation - pre-arbitration
  const [showPreArbForm, setShowPreArbForm] = useState(false);
  const [preArbEvidence, setPreArbEvidence] = useState<EvidenceInput>({ ...EMPTY_EVIDENCE });
  const [preArbLoading, setPreArbLoading] = useState(false);
  const [preArbError, setPreArbError] = useState<string | null>(null);

  // Escalation - arbitration
  const [arbLoading, setArbLoading] = useState(false);
  const [arbError, setArbError] = useState<string | null>(null);

  const fetchDispute = () => {
    if (!id) return;
    api
      .getDispute(id)
      .then((data) => {
        setDispute(data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  // Initial fetch + auto-refresh every 3s for processing cases
  useEffect(() => {
    let active = true;
    let interval: ReturnType<typeof setInterval> | null = null;

    const fetch = () => {
      if (!id || !active) return;
      api
        .getDispute(id)
        .then((data) => {
          if (active) {
            setDispute(data);
            setError(null);
          }
        })
        .catch((err) => {
          if (active) setError(err.message);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    };

    fetch();
    interval = setInterval(fetch, 3000);

    return () => {
      active = false;
      if (interval) clearInterval(interval);
    };
  }, [id]);

  // ---- Action handlers ----

  const handleAddEvidence = async () => {
    if (!id) return;
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      await api.addEvidence(id, evidenceForm);
      setEvidenceForm({ ...EMPTY_EVIDENCE });
      setShowEvidenceForm(false);
      fetchDispute();
    } catch (err: any) {
      setEvidenceError(err.message);
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleReview = async (approved: boolean) => {
    if (!id) return;
    setReviewLoading(true);
    setReviewError(null);
    try {
      await api.submitReview(id, approved, reviewNotes);
      setReviewNotes('');
      fetchDispute();
    } catch (err: any) {
      setReviewError(err.message);
    } finally {
      setReviewLoading(false);
    }
  };

  const handlePreArbitration = async () => {
    if (!id) return;
    setPreArbLoading(true);
    setPreArbError(null);
    try {
      await api.escalatePreArbitration(id, [preArbEvidence]);
      setPreArbEvidence({ ...EMPTY_EVIDENCE });
      setShowPreArbForm(false);
      fetchDispute();
    } catch (err: any) {
      setPreArbError(err.message);
    } finally {
      setPreArbLoading(false);
    }
  };

  const handleArbitration = async () => {
    if (!id) return;
    setArbLoading(true);
    setArbError(null);
    try {
      await api.escalateArbitration(id);
      fetchDispute();
    } catch (err: any) {
      setArbError(err.message);
    } finally {
      setArbLoading(false);
    }
  };

  // ---- Loading / Error states ----

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Clock className="h-5 w-5 text-gray-500 animate-spin mr-3" />
        <span className="text-gray-400">Loading dispute...</span>
      </div>
    );
  }

  if (error && !dispute) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4">
        <XCircle className="h-10 w-10 text-red-500" />
        <p className="text-gray-400">Dispute not found</p>
        <p className="text-sm text-red-400">{error}</p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!dispute) return null;

  const satisfiedCount = dispute.rule_evaluations.filter((r) => r.satisfied).length;
  const totalRules = dispute.rule_evaluations.length;

  const canAddEvidence = !['resolved', 'rejected', 'failed'].includes(dispute.stage);
  const showEscalation = ['resolved', 'decision'].includes(dispute.stage);

  return (
    <div className="space-y-6">
      {/* ====== HEADER ====== */}
      <div className="space-y-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <h1 className="text-xl font-bold text-white font-mono break-all">
            {dispute.case_id}
          </h1>
          <div className="flex items-center gap-2">
            <StageBadge stage={dispute.stage} />
            <ResolutionBadge resolution={dispute.resolution} />
          </div>
        </div>

        {dispute.requires_human_review && dispute.stage === 'human_review' && (
          <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded-lg px-4 py-3 text-amber-400">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium">
              This case requires human review before it can proceed.
            </span>
          </div>
        )}
      </div>

      {/* ====== INFO CARDS (2x2) ====== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Transaction */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <FileText className="h-5 w-5 text-gray-400" />
            Transaction
          </h3>
          <dl className="space-y-2">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Merchant</dt>
              <dd className="text-white text-sm">{dispute.merchant_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Amount</dt>
              <dd className="text-white text-sm font-mono">
                {dispute.transaction_amount.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {dispute.transaction_currency}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Transaction ID</dt>
              <dd className="text-white text-sm font-mono truncate max-w-[200px]">
                {dispute.transaction_id}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Environment</dt>
              <dd className="text-white text-sm">
                {ENVIRONMENTS[dispute.transaction_environment] || dispute.transaction_environment}
              </dd>
            </div>
          </dl>
        </div>

        {/* Classification */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Scale className="h-5 w-5 text-gray-400" />
            Classification
          </h3>
          <dl className="space-y-2">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Category</dt>
              <dd className="text-white text-sm">
                {dispute.category ? CATEGORIES[dispute.category] || dispute.category : '--'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Condition</dt>
              <dd className="text-white text-sm">{dispute.condition || '--'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Assigned Agent</dt>
              <dd className="text-white text-sm">
                {formatAgent(dispute.assigned_agent ?? dispute.decided_by)}
              </dd>
            </div>
          </dl>
        </div>

        {/* Decision */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            {dispute.resolution === 'issuer_win' ? (
              <ShieldCheck className="h-5 w-5 text-green-400" />
            ) : dispute.resolution === 'acquirer_win' ? (
              <ShieldX className="h-5 w-5 text-red-400" />
            ) : (
              <Scale className="h-5 w-5 text-gray-400" />
            )}
            Decision
          </h3>
          <dl className="space-y-2">
            <div className="flex justify-between items-center">
              <dt className="text-sm text-gray-400">Resolution</dt>
              <dd>
                <ResolutionBadge resolution={dispute.resolution} />
              </dd>
            </div>
            <div className="flex justify-between items-center">
              <dt className="text-sm text-gray-400">Confidence</dt>
              <dd>
                <ConfidenceMeter value={dispute.confidence} />
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Decided By</dt>
              <dd className="text-white text-sm">{formatAgent(dispute.decided_by)}</dd>
            </div>
            {dispute.rationale && (
              <div>
                <dt className="text-sm text-gray-400 mb-1">Rationale</dt>
                <dd className="text-white text-sm bg-gray-800/50 rounded p-2">
                  {dispute.rationale}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Timing */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Clock className="h-5 w-5 text-gray-400" />
            Timing
          </h3>
          <dl className="space-y-2">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Created</dt>
              <dd className="text-white text-sm">
                {new Date(dispute.created_at).toLocaleString()}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-400">Updated</dt>
              <dd className="text-white text-sm">
                {new Date(dispute.updated_at).toLocaleString()}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* ====== STAGE TIMELINE ====== */}
      {dispute.stage_history.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-4">Stage Timeline</h3>
          <div className="relative ml-1.5">
            {/* Vertical line */}
            <div className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-gray-700" />

            <div className="space-y-4">
              {dispute.stage_history.map((entry, i) => {
                const toStageInfo = STAGES[entry.to_stage] || { color: 'bg-gray-600', label: entry.to_stage };
                return (
                  <div key={i} className="relative flex items-start gap-4 pl-6">
                    {/* Dot */}
                    <div
                      className={`absolute left-0 top-1.5 w-3 h-3 rounded-full border-2 border-gray-900 ${toStageInfo.color}`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <StageBadge stage={entry.from_stage} />
                        <ChevronRight className="h-3 w-3 text-gray-500 shrink-0" />
                        <StageBadge stage={entry.to_stage} />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(entry.timestamp).toLocaleString()}
                      </p>
                      {entry.note && (
                        <p className="text-sm text-gray-400 mt-1">{entry.note}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ====== RULE EVALUATIONS ====== */}
      {dispute.rule_evaluations.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg">
          <button
            onClick={() => setRulesOpen(!rulesOpen)}
            className="w-full flex items-center justify-between p-5 text-left"
          >
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Scale className="h-5 w-5 text-gray-400" />
              Rule Evaluations
              <span className="text-sm font-normal text-gray-400">
                ({satisfiedCount}/{totalRules} satisfied)
              </span>
            </h3>
            <ChevronRight
              className={`h-5 w-5 text-gray-400 transition-transform ${
                rulesOpen ? 'rotate-90' : ''
              }`}
            />
          </button>

          {rulesOpen && (
            <div className="border-t border-gray-800 p-5 space-y-3">
              {dispute.rule_evaluations.map((rule, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 bg-gray-800/50 rounded-lg p-3"
                >
                  {rule.satisfied ? (
                    <CheckCircle2 className="h-5 w-5 text-green-400 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-white">
                        {rule.rule_section}
                      </span>
                      <span className="text-xs text-gray-500 font-mono">
                        {rule.rule_id}
                      </span>
                    </div>
                    <p className="text-sm text-gray-300">{rule.description}</p>
                    {rule.details && (
                      <p className="text-xs text-gray-500 mt-1">{rule.details}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ====== EVIDENCE LIST ====== */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <FileText className="h-5 w-5 text-gray-400" />
          Evidence
          <span className="text-sm font-normal text-gray-400">
            ({dispute.evidence.length})
          </span>
        </h3>

        {dispute.evidence.length === 0 ? (
          <p className="text-sm text-gray-500">No evidence submitted yet.</p>
        ) : (
          <div className="space-y-2">
            {dispute.evidence.map((ev, i) => (
              <div
                key={ev.evidence_id || i}
                className="flex items-start gap-3 bg-gray-800/50 rounded-lg p-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-300">
                      {ev.type}
                    </span>
                    <span className="text-xs text-gray-500">by {ev.provided_by}</span>
                    {ev.is_compelling && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-300">
                        ★ Compelling
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300">{ev.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add Evidence Form */}
        {canAddEvidence && (
          <div className="mt-4">
            {!showEvidenceForm ? (
              <button
                onClick={() => setShowEvidenceForm(true)}
                className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                <Send className="h-3.5 w-3.5" />
                Add Evidence
              </button>
            ) : (
              <div className="border border-gray-700 rounded-lg p-4 space-y-3">
                <h4 className="text-sm font-medium text-white">Add Evidence</h4>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    value={evidenceForm.description}
                    onChange={(e) =>
                      setEvidenceForm({ ...evidenceForm, description: e.target.value })
                    }
                    rows={2}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                    placeholder="Describe the evidence..."
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Evidence Type</label>
                    <input
                      type="text"
                      value={evidenceForm.evidence_type}
                      onChange={(e) =>
                        setEvidenceForm({ ...evidenceForm, evidence_type: e.target.value })
                      }
                      className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                      placeholder="e.g., receipt, statement"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Provided By</label>
                    <select
                      value={evidenceForm.provided_by}
                      onChange={(e) =>
                        setEvidenceForm({ ...evidenceForm, provided_by: e.target.value })
                      }
                      className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="issuer">Issuer</option>
                      <option value="acquirer">Acquirer</option>
                      <option value="cardholder">Cardholder</option>
                      <option value="merchant">Merchant</option>
                    </select>
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={evidenceForm.is_compelling_evidence}
                    onChange={(e) =>
                      setEvidenceForm({
                        ...evidenceForm,
                        is_compelling_evidence: e.target.checked,
                      })
                    }
                    className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
                  />
                  Compelling evidence
                </label>

                {evidenceError && (
                  <p className="text-sm text-red-400">{evidenceError}</p>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleAddEvidence}
                    disabled={evidenceLoading || !evidenceForm.description}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium text-white transition-colors"
                  >
                    {evidenceLoading ? (
                      <Clock className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Send className="h-3.5 w-3.5" />
                    )}
                    {evidenceLoading ? 'Adding...' : 'Submit'}
                  </button>
                  <button
                    onClick={() => {
                      setShowEvidenceForm(false);
                      setEvidenceError(null);
                    }}
                    className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ====== PROCESSING NOTES ====== */}
      {dispute.processing_notes.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3">
            Processing Notes
            <span className="text-sm font-normal text-gray-400 ml-2">
              ({dispute.processing_notes.length})
            </span>
          </h3>
          <div className="space-y-2">
            {dispute.processing_notes.map((note, i) => (
              <div key={i} className="bg-gray-800/50 rounded p-3">
                <p className="text-sm text-gray-300 font-mono whitespace-pre-wrap">{note}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ====== HUMAN REVIEW PANEL ====== */}
      {dispute.stage === 'human_review' && (
        <div className="bg-gray-900 border border-amber-500/40 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Human Review Required
          </h3>
          <p className="text-sm text-gray-400 mb-4">
            Review the dispute details above and approve or reject this case.
          </p>

          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Reviewer Notes</label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
                placeholder="Enter your review notes..."
              />
            </div>

            {reviewError && (
              <p className="text-sm text-red-400">{reviewError}</p>
            )}

            <div className="flex items-center gap-3">
              <button
                onClick={() => handleReview(true)}
                disabled={reviewLoading}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium text-white transition-colors"
              >
                {reviewLoading ? (
                  <Clock className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Approve
              </button>
              <button
                onClick={() => handleReview(false)}
                disabled={reviewLoading}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium text-white transition-colors"
              >
                {reviewLoading ? (
                  <Clock className="h-4 w-4 animate-spin" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ====== ESCALATION PANEL ====== */}
      {showEscalation && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-400" />
            Escalation Options
          </h3>

          <div className="space-y-4">
            {/* Pre-Arbitration */}
            <div className="border border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-white">
                  Escalate to Pre-Arbitration
                </h4>
                {!showPreArbForm && (
                  <button
                    onClick={() => setShowPreArbForm(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-orange-600 hover:bg-orange-500 rounded text-sm font-medium text-white transition-colors"
                  >
                    Escalate
                  </button>
                )}
              </div>

              {showPreArbForm && (
                <div className="space-y-3 mt-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      Evidence Description
                    </label>
                    <textarea
                      value={preArbEvidence.description}
                      onChange={(e) =>
                        setPreArbEvidence({ ...preArbEvidence, description: e.target.value })
                      }
                      rows={2}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                      placeholder="Describe the evidence for pre-arbitration..."
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">
                        Evidence Type
                      </label>
                      <input
                        type="text"
                        value={preArbEvidence.evidence_type}
                        onChange={(e) =>
                          setPreArbEvidence({
                            ...preArbEvidence,
                            evidence_type: e.target.value,
                          })
                        }
                        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                        placeholder="e.g., receipt, statement"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Provided By</label>
                      <select
                        value={preArbEvidence.provided_by}
                        onChange={(e) =>
                          setPreArbEvidence({
                            ...preArbEvidence,
                            provided_by: e.target.value,
                          })
                        }
                        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-orange-500"
                      >
                        <option value="issuer">Issuer</option>
                        <option value="acquirer">Acquirer</option>
                        <option value="cardholder">Cardholder</option>
                        <option value="merchant">Merchant</option>
                      </select>
                    </div>
                  </div>

                  <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={preArbEvidence.is_compelling_evidence}
                      onChange={(e) =>
                        setPreArbEvidence({
                          ...preArbEvidence,
                          is_compelling_evidence: e.target.checked,
                        })
                      }
                      className="rounded border-gray-600 bg-gray-800 text-orange-500 focus:ring-orange-500"
                    />
                    Compelling evidence
                  </label>

                  {preArbError && (
                    <p className="text-sm text-red-400">{preArbError}</p>
                  )}

                  <div className="flex items-center gap-2">
                    <button
                      onClick={handlePreArbitration}
                      disabled={preArbLoading || !preArbEvidence.description}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium text-white transition-colors"
                    >
                      {preArbLoading ? (
                        <Clock className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Send className="h-3.5 w-3.5" />
                      )}
                      {preArbLoading ? 'Submitting...' : 'Submit Pre-Arbitration'}
                    </button>
                    <button
                      onClick={() => {
                        setShowPreArbForm(false);
                        setPreArbError(null);
                      }}
                      className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Arbitration */}
            <div className="border border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-white">
                    Escalate to Arbitration
                  </h4>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Final escalation step. This action cannot be undone.
                  </p>
                </div>
                <button
                  onClick={handleArbitration}
                  disabled={arbLoading}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm font-medium text-white transition-colors"
                >
                  {arbLoading ? (
                    <Clock className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  )}
                  {arbLoading ? 'Escalating...' : 'Escalate'}
                </button>
              </div>
              {arbError && (
                <p className="text-sm text-red-400 mt-2">{arbError}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
