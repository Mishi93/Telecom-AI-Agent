export interface Customer {
  customer_id: string;
  name: string;
}

export interface CustomerDetail {
  customer_id: string;
  name: string;
  balance: number;
  data_remaining: string;
  minutes_remaining: number;
}

export interface Complaint {
  ticket_id: string;
  issue_type: string;
  priority: string;
  description: string;
  status: string;
  created_at: string | null;
}

export interface ChurnPrediction {
  customer_id: string;
  churn_risk: boolean;
  churn_probability: number;
  label: string;
}

export interface PackagePrediction {
  customer_id: string;
  recommended_tier: string;
  tier_probabilities: Record<string, number>;
}

export interface AnalyticsSummary {
  total_customers: number;
  total_complaints: number;
  open_tickets?: number;
  resolved_tickets?: number;
  complaints_by_issue_type: Record<string, number>;
  complaints_by_priority: Record<string, number>;
  complaints_by_status: Record<string, number>;
  churn_risk_distribution: Record<string, number>;
  package_tier_distribution: Record<string, number>;
  prediction_errors: number;
}

export interface ApiErrorDetail {
  detail?: string;
}
