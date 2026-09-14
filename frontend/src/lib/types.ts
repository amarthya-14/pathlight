// Types mirror backend/app/schemas/*.py exactly (field names/shapes) — this is the
// "hand-written typed fetch wrapper" alternative to OpenAPI codegen mentioned in
// docs/ARCHITECTURE.md §8's Gate 8 scope. Keep these in sync by hand when a schema
// changes; there's no build-time check tying the two together yet.

export type UserOut = {
  id: string;
  email: string;
  full_name: string | null;
};

export type ProfileOut = {
  id: string | null;
  user_id: string;
  cgpa: number | null;
  branch: string | null;
  github_username: string | null;
};

export type ProfileUpsert = {
  cgpa: number | null;
  branch: string | null;
  github_username: string | null;
};

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
  | "REJECTED";

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

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}
