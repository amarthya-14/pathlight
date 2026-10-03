import type { ApplicationOut, ApplicationStage } from "./types";
import type { Tone } from "@/components/ui";

// One place for how each application stage is named and colored, used by the list,
// timeline, dashboard and detail stepper so they never disagree.
export const STAGE_META: Record<ApplicationStage, { label: string; tone: Tone }> = {
  DISCOVERED: { label: "Discovered", tone: "neutral" },
  ELIGIBILITY_CHECKED: { label: "Eligibility checked", tone: "info" },
  PREPARING: { label: "Preparing", tone: "accent" },
  READY_TO_APPLY: { label: "Ready to review", tone: "accent" },
  APPLIED: { label: "Applied", tone: "ok" },
  OA: { label: "Online assessment", tone: "warn" },
  INTERVIEW: { label: "Interview", tone: "warn" },
  OFFER: { label: "Offer", tone: "ok" },
  REJECTED: { label: "Rejected", tone: "bad" },
  MANUAL_APPLY_REQUIRED: { label: "Finish applying", tone: "warn" },
  SKIPPED_BY_USER: { label: "Skipped", tone: "neutral" },
};

export function currentStage(app: ApplicationOut): ApplicationStage | null {
  return app.status_history.at(-1)?.stage ?? null;
}

// The main happy path shown as a progress stepper on the detail page.
export const JOURNEY: { key: string; label: string; stages: ApplicationStage[] }[] = [
  { key: "found", label: "Found", stages: ["DISCOVERED"] },
  { key: "checked", label: "Checked", stages: ["ELIGIBILITY_CHECKED"] },
  { key: "prep", label: "Prep plan", stages: ["PREPARING"] },
  { key: "ready", label: "Tailored", stages: ["READY_TO_APPLY"] },
  { key: "applied", label: "Applied", stages: ["APPLIED", "MANUAL_APPLY_REQUIRED", "OA", "INTERVIEW", "OFFER", "REJECTED"] },
];

export function journeyIndex(app: ApplicationOut): number {
  let reached = -1;
  for (const event of app.status_history) {
    const idx = JOURNEY.findIndex((step) => step.stages.includes(event.stage));
    if (idx > reached) reached = idx;
  }
  return reached;
}

export function daysUntil(deadline: string): number {
  return Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
}

export function deadlineTone(days: number): Tone {
  if (days < 0) return "neutral";
  if (days <= 3) return "bad";
  if (days <= 14) return "warn";
  return "neutral";
}

export function deadlineLabel(days: number): string {
  if (days < 0) return "Closed";
  if (days === 0) return "Due today";
  if (days === 1) return "1 day left";
  return `${days} days left`;
}

/** Jobs that arrived from a job-alert email — via the Gmail integration or forwarding. */
export function isAlertSource(source: string | null | undefined): boolean {
  return source === "gmail_mcp" || source === "email_forward";
}
