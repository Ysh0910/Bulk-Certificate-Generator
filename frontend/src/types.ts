export interface RecipientExtraFields {
  blood_group?: string;
  donation_date?: string;
  camp_name?: string;
  organization?: string;
  units_donated?: string;
}

export interface RecipientInput {
  name: string;
  email: string;
  extra_fields: RecipientExtraFields;
}

export interface Recipient {
  id: string;
  name: string;
  email: string;
  status: "PENDING" | "SUCCESS" | "FAILED";
  error_message: string | null;
  generated_at: string | null;
}

export interface JobStatus {
  id: string;
  created_at: string;
  total_count: number;
  success_count: number;
  failure_count: number;
  pending_count: number;
  overall_status: "PENDING" | "PROCESSING" | "COMPLETED" | "COMPLETED_WITH_ERRORS" | "FAILED";
}

export interface JobCreateResponse {
  id: string;
  total_count: number;
}
