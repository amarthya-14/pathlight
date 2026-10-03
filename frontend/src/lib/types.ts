// Types mirror backend/app/schemas/*.py exactly (field names/shapes) — this is the
// "hand-written typed fetch wrapper" alternative to OpenAPI codegen mentioned in
// docs/ARCHITECTURE.md §8's Gate 8 scope. Keep these in sync by hand when a schema
// changes; there's no build-time check tying the two together yet.

export type UserOut = {
  id: string;
  email: string;
  full_name: string | null;
  is_admin?: boolean;
  ai_keys?: AiKeyOut[];
};

export type AiProviderId = "gemini" | "groq" | "openai" | "anthropic" | "custom";

export type AiKeyOut = {
  provider: AiProviderId;
  last4: string;
  strong_model: string;
  small_model: string;
  base_url: string | null;
  added_at: string;
};

export type ProfileOut = {
  id: string | null;
  user_id: string;
  cgpa: number | null;
  branch: string | null;
  github_username: string | null;
  experience_years: number | null;
  college: string | null;
  graduation_year: number | null;
  target_roles: string[];
  preferred_locations: string[];
  open_to_remote: boolean;
  expected_ctc_lpa: number | null;
  notice_period: string | null;
  autopilot_enabled: boolean;
  autopilot_min_match: number;
  autopilot_last_run: string | null;
};

export type ProfileUpsert = {
  cgpa: number | null;
  branch: string | null;
  github_username: string | null;
  experience_years?: number | null;
  college?: string | null;
  graduation_year?: number | null;
  target_roles?: string[];
  preferred_locations?: string[];
  open_to_remote?: boolean;
  expected_ctc_lpa?: number | null;
  notice_period?: string | null;
  autopilot_enabled?: boolean;
  autopilot_min_match?: number;
};

export type PostApplyStage = "OA" | "INTERVIEW" | "OFFER" | "REJECTED";

export type EligibilityDecision = "eligible" | "partially_eligible" | "not_eligible" | "uncertain";

export type EligibilityResult = {
  decision: EligibilityDecision;
  reason: string;
  evidence: string[];
  missing_information: string[];
  confidence: number;
};

export type SkillGapResult = {
  matched: string[];
  weak: string[];
  missing: string[];
  github_evidence: Record<string, string[]>;
  github_unavailable: boolean;
};

export type ApplicationStage =
  | "DISCOVERED"
  | "ELIGIBILITY_CHECKED"
  | "PREPARING"
  | "READY_TO_APPLY"
  | "APPLIED"
  | "OA"
  | "INTERVIEW"
  | "OFFER"
  | "REJECTED"
  | "MANUAL_APPLY_REQUIRED"
  | "SKIPPED_BY_USER";

export type ApplicationStatusEvent = {
  stage: ApplicationStage;
  note: string | null;
  created_at: string;
};

export type ApplicationOut = {
  id: string;
  opportunity_id: string;
  company_name: string;
  role: string;
  deadline: string | null;
  source: string | null;
  apply_email: string | null;
  application_url: string | null;
  min_experience_years: number | null;
  has_job_description: boolean;
  eligibility: EligibilityResult | null;
  skill_gap: SkillGapResult | null;
  skill_gap_note: string | null;
  status_history: ApplicationStatusEvent[];
  created_at: string;
};

export type TaskStatus = "not_started" | "in_progress" | "done";

export type PreparationTaskOut = {
  id: string;
  skill: string;
  title: string;
  description: string;
  depends_on: string[];
  estimated_hours: number;
  status: TaskStatus;
  order_index: number;
};

export type PreparationPlanOut = {
  id: string;
  application_id: string;
  opportunity_id: string;
  deadline: string | null;
  available_hours: number | null;
  total_estimated_hours: number;
  feasible: boolean | null;
  tasks: PreparationTaskOut[];
  generated_at: string;
};

export type DashboardHomeOut = {
  recent_applications: ApplicationOut[];
  urgent_deadlines: ApplicationOut[];
  total_missing_skills: number;
  total_weak_skills: number;
  most_common_missing_skills: string[];
  has_profile: boolean;
  has_resume: boolean;
};

export type DocumentType = "resume" | "job_description" | "email_paste" | "other";

export type DocumentOut = {
  id: string;
  doc_type: DocumentType;
  original_filename: string;
  content_type: string;
  created_at: string;
};

export type DocumentDetailOut = DocumentOut & {
  storage_filename: string;
  extracted_text: string | null;
};

export type IngestResponse = {
  opportunity_id: string;
  application_id: string;
  company_name: string;
  role: string;
  eligibility: EligibilityResult | null;
  skill_gap: SkillGapResult | null;
  skill_gap_note: string | null;
  needs_human_review: boolean;
  error: string | null;
};

// Gate 10 — autonomous applications (backend/app/schemas/application.py, integration.py)

export type TailoredResumeOut = {
  application_id: string;
  base_document_id: string;
  base_resume_text: string | null;
  tailored_text: string;
  cover_note: string;
  changes_summary: string[];
  skills_emphasized: string[];
  confidence: number;
  warnings: string[];
  ats: AtsReport | null;
  generated_at: string;
};

// backend/app/core/ats.py — deterministic ATS score of the tailored resume.
export type AtsReport = {
  score: number;
  breakdown: Record<"keywords" | "job_title" | "sections" | "contact" | "format" | "impact", number>;
  matched_keywords: string[];
  fixable_keywords: string[];
  missing_keywords: string[];
  blocked_points: number;
  suggestions: string[];
};

export type ReviewOutcome = "applied" | "manual_apply_required" | "skipped";

export type ReviewResponse = {
  outcome: ReviewOutcome;
  detail: string;
  sent_to: string | null;
  application_url: string | null;
  application: ApplicationOut;
};

export type IntegrationOut = {
  provider: string;
  status: "connected" | "error";
  scopes: string[];
  account_email: string | null;
  connected_at: string;
  last_polled_at: string | null;
  last_error: string | null;
};

export type GmailSyncOut = {
  messages_seen: number;
  opportunities_ingested: number;
  skipped_already_processed: number;
  skipped_not_relevant: number;
  failures: string[];
};

export type GmailSyncStatus = {
  state: "idle" | "running" | "done" | "error";
  started_at: string | null;
  result: GmailSyncOut | null;
  error: string | null;
};

// backend/app/api/routes/jobs.py — the job-board feed.
export type JobFeedItem = {
  id: string;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  url: string;
  source: string;
  posted_at: string | null;
  match: number;
  matched_skills: string[];
  missing_skills: string[];
  reasons: string[];
  min_experience: number | null;
  entry_level: boolean;
  tracked_application_id: string | null;
};

export type JobFeedOut = {
  items: JobFeedItem[];
  total_listings: number;
  matching: number;
  hidden: Record<"field" | "experience" | "batch" | "old" | "low_match" | "dismissed", number>;
  refreshed_at: string | null;
  refreshing: boolean;
  personalized: boolean;
  families: string[];
  sources: number;
};

export type JobFeedParams = { q?: string; minMatch?: number; days?: number; includeExperienced?: boolean };

export type ApplicationKit = {
  answers: { question: string; answer: string; note: string }[];
  connection_note: string;
  referral_message: string;
  search_links: { label: string; url: string }[];
};

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}
