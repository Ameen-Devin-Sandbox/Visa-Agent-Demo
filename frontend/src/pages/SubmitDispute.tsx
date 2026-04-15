import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, AlertCircle } from 'lucide-react';
import { api } from '../lib/api';
import type { DisputeSubmitRequest, EvidenceInput } from '../lib/types';

const inputClass =
  'w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent';
const labelClass = 'block text-sm font-medium text-gray-400 mb-1';
const sectionClass = 'bg-gray-900 border border-gray-800 rounded-lg p-6 mb-6';
const sectionTitle = 'text-lg font-semibold text-white mb-4';
const checkboxClass = 'rounded bg-gray-800 border-gray-600 text-blue-500 focus:ring-blue-500';

interface EvidenceRow {
  description: string;
  evidence_type: string;
  provided_by: string;
  is_compelling_evidence: boolean;
}

export default function SubmitDispute() {
  const navigate = useNavigate();

  // Transaction fields
  const [transactionId, setTransactionId] = useState('');
  const [transactionDate, setTransactionDate] = useState('');
  const [processingDate, setProcessingDate] = useState('');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [merchantName, setMerchantName] = useState('');
  const [merchantCategoryCode, setMerchantCategoryCode] = useState('5411');
  const [merchantCountry, setMerchantCountry] = useState('US');
  const [environment, setEnvironment] = useState('ecommerce');
  const [isRecurring, setIsRecurring] = useState(false);
  const [isChipCard, setIsChipCard] = useState(false);
  const [cvvPresent, setCvvPresent] = useState(false);
  const [threeDSecure, setThreeDSecure] = useState(false);
  const [authorizationCode, setAuthorizationCode] = useState('');

  // Cardholder fields
  const [cardholderName, setCardholderName] = useState('');
  const [partialPaymentCredential, setPartialPaymentCredential] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [cardholderStatement, setCardholderStatement] = useState('');

  // Evidence
  const [evidenceRows, setEvidenceRows] = useState<EvidenceRow[]>([]);

  // Additional options
  const [fraudTypeCode, setFraudTypeCode] = useState('');
  const [priority, setPriority] = useState('3');
  const [issuerCertification, setIssuerCertification] = useState('');

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addEvidence() {
    setEvidenceRows((prev) => [
      ...prev,
      { description: '', evidence_type: '', provided_by: 'issuer', is_compelling_evidence: false },
    ]);
  }

  function updateEvidence(index: number, field: keyof EvidenceRow, value: string | boolean) {
    setEvidenceRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  }

  function removeEvidence(index: number) {
    setEvidenceRows((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const evidence: EvidenceInput[] = evidenceRows.map((r) => ({
      description: r.description,
      evidence_type: r.evidence_type,
      provided_by: r.provided_by,
      is_compelling_evidence: r.is_compelling_evidence,
    }));

    const data: DisputeSubmitRequest = {
      transaction: {
        transaction_id: transactionId,
        transaction_date: transactionDate,
        processing_date: processingDate,
        amount: parseFloat(amount),
        currency,
        merchant_name: merchantName,
        merchant_category_code: merchantCategoryCode,
        merchant_country: merchantCountry,
        environment,
        is_recurring: isRecurring,
        is_chip_card: isChipCard,
        cvv_present: cvvPresent,
        three_d_secure_authenticated: threeDSecure,
        authorization_code: authorizationCode,
      },
      cardholder: {
        cardholder_name: cardholderName,
        partial_payment_credential: partialPaymentCredential,
        contact_email: contactEmail,
        cardholder_statement: cardholderStatement,
      },
      evidence,
      fraud_type_code: fraudTypeCode || null,
      priority,
      issuer_certification: issuerCertification || null,
    };

    try {
      const result = await api.submitDispute(data);
      navigate(`/disputes/${result.case_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Submit New Dispute</h1>

      <form onSubmit={handleSubmit}>
        {/* ── Section 1: Transaction Details ── */}
        <div className={sectionClass}>
          <h2 className={sectionTitle}>Transaction Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Transaction ID *</label>
              <input
                type="text"
                required
                className={inputClass}
                value={transactionId}
                onChange={(e) => setTransactionId(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Transaction Date *</label>
              <input
                type="date"
                required
                className={inputClass}
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Processing Date *</label>
              <input
                type="date"
                required
                className={inputClass}
                value={processingDate}
                onChange={(e) => setProcessingDate(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Amount *</label>
              <input
                type="number"
                required
                step="0.01"
                className={inputClass}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Currency</label>
              <input
                type="text"
                maxLength={3}
                className={inputClass}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              />
            </div>
            <div>
              <label className={labelClass}>Merchant Name *</label>
              <input
                type="text"
                required
                className={inputClass}
                value={merchantName}
                onChange={(e) => setMerchantName(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Merchant Category Code</label>
              <input
                type="text"
                className={inputClass}
                value={merchantCategoryCode}
                onChange={(e) => setMerchantCategoryCode(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Merchant Country</label>
              <input
                type="text"
                className={inputClass}
                value={merchantCountry}
                onChange={(e) => setMerchantCountry(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Environment</label>
              <select
                className={inputClass}
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
              >
                <option value="ecommerce">E-Commerce</option>
                <option value="card_present">Card Present</option>
                <option value="card_absent">Card Absent</option>
                <option value="atm">ATM</option>
                <option value="mail_order_telephone_order">Mail/Phone Order</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Authorization Code</label>
              <input
                type="text"
                className={inputClass}
                value={authorizationCode}
                onChange={(e) => setAuthorizationCode(e.target.value)}
              />
            </div>
          </div>

          {/* Checkbox row */}
          <div className="flex flex-wrap gap-6 mt-4">
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                className={checkboxClass}
                checked={isRecurring}
                onChange={(e) => setIsRecurring(e.target.checked)}
              />
              Recurring
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                className={checkboxClass}
                checked={isChipCard}
                onChange={(e) => setIsChipCard(e.target.checked)}
              />
              Chip Card
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                className={checkboxClass}
                checked={cvvPresent}
                onChange={(e) => setCvvPresent(e.target.checked)}
              />
              CVV Present
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                className={checkboxClass}
                checked={threeDSecure}
                onChange={(e) => setThreeDSecure(e.target.checked)}
              />
              3-D Secure Authenticated
            </label>
          </div>
        </div>

        {/* ── Section 2: Cardholder Info ── */}
        <div className={sectionClass}>
          <h2 className={sectionTitle}>Cardholder Info</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Cardholder Name *</label>
              <input
                type="text"
                required
                className={inputClass}
                value={cardholderName}
                onChange={(e) => setCardholderName(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Partial Payment Credential *</label>
              <input
                type="text"
                required
                placeholder="e.g. last 4 of card"
                className={inputClass}
                value={partialPaymentCredential}
                onChange={(e) => setPartialPaymentCredential(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Contact Email</label>
              <input
                type="email"
                className={inputClass}
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
              />
            </div>
          </div>
          <div className="mt-4">
            <label className={labelClass}>Cardholder Statement</label>
            <textarea
              rows={3}
              className={inputClass}
              value={cardholderStatement}
              onChange={(e) => setCardholderStatement(e.target.value)}
            />
          </div>
        </div>

        {/* ── Section 3: Evidence ── */}
        <div className={sectionClass}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Evidence</h2>
            <button
              type="button"
              onClick={addEvidence}
              className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              + Add Evidence
            </button>
          </div>

          {evidenceRows.length === 0 && (
            <p className="text-sm text-gray-500">No evidence added yet.</p>
          )}

          {evidenceRows.map((row, i) => (
            <div
              key={i}
              className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end mb-3 p-3 bg-gray-800/50 rounded-md border border-gray-700/50"
            >
              <div className="md:col-span-4">
                <label className={labelClass}>Description</label>
                <input
                  type="text"
                  className={inputClass}
                  value={row.description}
                  onChange={(e) => updateEvidence(i, 'description', e.target.value)}
                />
              </div>
              <div className="md:col-span-2">
                <label className={labelClass}>Type</label>
                <input
                  type="text"
                  className={inputClass}
                  value={row.evidence_type}
                  onChange={(e) => updateEvidence(i, 'evidence_type', e.target.value)}
                />
              </div>
              <div className="md:col-span-2">
                <label className={labelClass}>Provided By</label>
                <select
                  className={inputClass}
                  value={row.provided_by}
                  onChange={(e) => updateEvidence(i, 'provided_by', e.target.value)}
                >
                  <option value="issuer">Issuer</option>
                  <option value="acquirer">Acquirer</option>
                </select>
              </div>
              <div className="md:col-span-2 flex items-center gap-2 pt-5">
                <input
                  type="checkbox"
                  className={checkboxClass}
                  checked={row.is_compelling_evidence}
                  onChange={(e) => updateEvidence(i, 'is_compelling_evidence', e.target.checked)}
                />
                <span className="text-sm text-gray-300">Compelling</span>
              </div>
              <div className="md:col-span-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => removeEvidence(i)}
                  className="text-sm text-red-400 hover:text-red-300 transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* ── Section 4: Additional Options ── */}
        <div className={sectionClass}>
          <h2 className={sectionTitle}>Additional Options</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Fraud Type Code</label>
              <select
                className={inputClass}
                value={fraudTypeCode}
                onChange={(e) => setFraudTypeCode(e.target.value)}
              >
                <option value="">None</option>
                <option value="0">0 – Lost</option>
                <option value="1">1 – Stolen</option>
                <option value="2">2 – Not Received</option>
                <option value="4">4 – Counterfeit</option>
                <option value="7">7 – Account Takeover</option>
                <option value="C">C – Merchant Misrepresentation</option>
                <option value="D">D – Manipulation</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Priority</label>
              <select
                className={inputClass}
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="1">Critical</option>
                <option value="2">High</option>
                <option value="3">Medium</option>
                <option value="4">Low</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Issuer Certification</label>
              <input
                type="text"
                className={inputClass}
                value={issuerCertification}
                onChange={(e) => setIssuerCertification(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* ── Error Alert ── */}
        {error && (
          <div className="flex items-start gap-3 bg-red-900/30 border border-red-800 rounded-lg p-4 mb-6">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* ── Submit Button ── */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {submitting ? (
            <>
              <svg
                className="animate-spin h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Submitting…
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit Dispute
            </>
          )}
        </button>
      </form>
    </div>
  );
}
