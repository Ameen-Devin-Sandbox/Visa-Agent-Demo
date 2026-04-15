export interface HealthResponse {
  status: string;
  version: string;
  agents_loaded: number;
  queue_depth: number;
}

export interface QueueStatsResponse {
  queue_depth: Record<string, number>;
  stats: Record<string, number>;
}

export interface DisputeSummary {
  case_id: string;
  stage: string;
  category: string | null;
  condition: string | null;
  resolution: string | null;
  confidence: number | null;
  requires_human_review: boolean | null;
  assigned_agent: string | null;
  rule_evaluations_count: number;
  evidence_count: number;
  processing_notes_count: number;
  created_at: string;
  updated_at: string;
}

export interface RuleEvaluation {
  rule_id: string;
  rule_section: string;
  description: string;
  satisfied: boolean;
  details: string;
}

export interface Evidence {
  evidence_id: string;
  description: string;
  type: string;
  provided_by: string;
  is_compelling: boolean;
}

export interface StageTransition {
  from_stage: string;
  to_stage: string;
  timestamp: string;
  note: string;
}

export interface DisputeDetail {
  case_id: string;
  stage: string;
  category: string | null;
  condition: string | null;
  transaction_id: string;
  transaction_amount: number;
  transaction_currency: string;
  merchant_name: string;
  transaction_environment: string;
  resolution: string | null;
  rationale: string | null;
  confidence: number | null;
  requires_human_review: boolean;
  decided_by: string | null;
  assigned_agent: string | null;
  rule_evaluations: RuleEvaluation[];
  evidence: Evidence[];
  processing_notes: string[];
  stage_history: StageTransition[];
  created_at: string;
  updated_at: string;
}

export interface TransactionInput {
  transaction_id: string;
  transaction_date: string;
  processing_date: string;
  amount: number;
  currency: string;
  merchant_name: string;
  merchant_category_code: string;
  merchant_country: string;
  environment: string;
  is_recurring: boolean;
  is_chip_card: boolean;
  cvv_present: boolean;
  three_d_secure_authenticated: boolean;
  authorization_code: string;
}

export interface CardholderInput {
  cardholder_name: string;
  partial_payment_credential: string;
  contact_email: string;
  cardholder_statement: string;
}

export interface EvidenceInput {
  description: string;
  evidence_type: string;
  provided_by: string;
  is_compelling_evidence: boolean;
}

export interface DisputeSubmitRequest {
  transaction: TransactionInput;
  cardholder: CardholderInput;
  fraud_type_code?: string | null;
  evidence: EvidenceInput[];
  issuer_certification?: string | null;
  dispute_amount?: number | null;
  dispute_currency?: string | null;
  priority: string;
}

export const CATEGORIES: Record<string, string> = {
  '10': 'Fraud',
  '11': 'Authorization',
  '12': 'Processing Errors',
  '13': 'Consumer Disputes',
};

export const STAGES: Record<string, { label: string; color: string }> = {
  intake: { label: 'Intake', color: 'bg-gray-500' },
  validation: { label: 'Validation', color: 'bg-blue-500' },
  categorization: { label: 'Categorization', color: 'bg-indigo-500' },
  rule_evaluation: { label: 'Rule Evaluation', color: 'bg-purple-500' },
  processing: { label: 'Processing', color: 'bg-yellow-500' },
  decision: { label: 'Decision', color: 'bg-orange-500' },
  pre_arbitration: { label: 'Pre-Arbitration', color: 'bg-red-400' },
  pre_arbitration_response: { label: 'Pre-Arb Response', color: 'bg-red-500' },
  arbitration: { label: 'Arbitration', color: 'bg-red-700' },
  resolved: { label: 'Resolved', color: 'bg-green-600' },
  rejected: { label: 'Rejected', color: 'bg-red-600' },
  human_review: { label: 'Human Review', color: 'bg-amber-500' },
  failed: { label: 'Failed', color: 'bg-red-800' },
};

export const RESOLUTIONS: Record<string, { label: string; color: string }> = {
  issuer_win: { label: 'Issuer Win', color: 'text-green-400' },
  acquirer_win: { label: 'Acquirer Win', color: 'text-red-400' },
  split_liability: { label: 'Split Liability', color: 'text-yellow-400' },
  withdrawn: { label: 'Withdrawn', color: 'text-gray-400' },
  escalated_pre_arbitration: { label: 'Escalated (Pre-Arb)', color: 'text-orange-400' },
  escalated_arbitration: { label: 'Escalated (Arbitration)', color: 'text-red-400' },
  human_override: { label: 'Human Override', color: 'text-purple-400' },
  invalid_dispute: { label: 'Invalid', color: 'text-gray-500' },
};

export const ENVIRONMENTS: Record<string, string> = {
  card_present: 'Card Present',
  card_absent: 'Card Absent',
  atm: 'ATM',
  ecommerce: 'E-Commerce',
  mail_order_telephone_order: 'Mail/Phone Order',
};
