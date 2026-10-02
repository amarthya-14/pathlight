import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { reviewMock } = vi.hoisted(() => ({ reviewMock: vi.fn() }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { reviewApplication: reviewMock } };
});

import { ApiError } from "@/lib/api";
import type { ApplicationOut, TailoredResumeOut } from "@/lib/types";
import { ReviewApplyCard } from "./ReviewApplyCard";

function makeApp(overrides: Partial<ApplicationOut> = {}): ApplicationOut {
  return {
    id: "app1",
    opportunity_id: "opp1",
    company_name: "Acme",
    role: "Backend Intern",
    deadline: null,
    source: "gmail_mcp",
    apply_email: "jobs@acme.dev",
    application_url: null,
    eligibility: null,
    skill_gap: null,
    skill_gap_note: null,
    status_history: [{ stage: "READY_TO_APPLY", note: null, created_at: "2026-10-01T00:00:00Z" }],
    created_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

const TAILORED: TailoredResumeOut = {
  application_id: "app1",
  base_document_id: "doc1",
  base_resume_text: "Name\nSkills: Python",
  tailored_text: "Name\nSkills: Python (primary)",
  cover_note: "Dear Hiring Team, hello.",
  changes_summary: ["Highlighted Python"],
  skills_emphasized: ["Python"],
  confidence: 0.8,
  warnings: ["Posting requires Kubernetes — not on your resume, so it was not added."],
  generated_at: "2026-10-01T00:00:00Z",
};

describe("ReviewApplyCard", () => {
  beforeEach(() => {
    // Block body on purpose: a function returned from beforeEach is run as a teardown
    // hook, and mockReset() returns the mock itself.
    reviewMock.mockReset();
  });

  it("shows the diff, cover note, and warnings", () => {
    render(<ReviewApplyCard application={makeApp()} tailored={TAILORED} onReviewed={vi.fn()} />);
    const diff = screen.getByTestId("resume-diff");
    expect(diff.querySelector('[data-diff="added"]')?.textContent).toContain("Skills: Python (primary)");
    expect(diff.querySelector('[data-diff="removed"]')?.textContent).toContain("Skills: Python");
    expect(screen.getByText("Dear Hiring Team, hello.")).toBeInTheDocument();
    expect(screen.getByText(/requires Kubernetes/)).toBeInTheDocument();
  });

  it("requires an explicit confirm naming the recipient before sending", async () => {
    const onReviewed = vi.fn();
    reviewMock.mockResolvedValue({ outcome: "applied" });
    render(<ReviewApplyCard application={makeApp()} tailored={TAILORED} onReviewed={onReviewed} />);

    fireEvent.click(screen.getByText("Approve & send"));
    expect(reviewMock).not.toHaveBeenCalled();
    expect(screen.getByText(/Send this application to/)).toHaveTextContent("jobs@acme.dev");

    fireEvent.click(screen.getByText("Yes, send it"));
    await waitFor(() => expect(onReviewed).toHaveBeenCalled());
    expect(reviewMock).toHaveBeenCalledWith("app1", true);
  });

  it("skip calls review with approve=false", async () => {
    reviewMock.mockResolvedValue({ outcome: "skipped" });
    render(<ReviewApplyCard application={makeApp()} tailored={TAILORED} onReviewed={vi.fn()} />);
    fireEvent.click(screen.getByText("Skip"));
    await waitFor(() => expect(reviewMock).toHaveBeenCalledWith("app1", false));
  });

  it("offers manual apply without a send confirm when there's no apply email", async () => {
    reviewMock.mockResolvedValue({ outcome: "manual_apply_required" });
    render(
      <ReviewApplyCard application={makeApp({ apply_email: null })} tailored={TAILORED} onReviewed={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Approve — I'll apply manually"));
    await waitFor(() => expect(reviewMock).toHaveBeenCalledWith("app1", true));
  });

  it("surfaces backend errors such as Gmail not connected", async () => {
    reviewMock.mockRejectedValue(
      new ApiError(409, "Connect Gmail (with send permission) on the Integrations page before approving.")
    );
    render(<ReviewApplyCard application={makeApp()} tailored={TAILORED} onReviewed={vi.fn()} />);
    fireEvent.click(screen.getByText("Approve & send"));
    fireEvent.click(screen.getByText("Yes, send it"));
    expect(await screen.findByText(/Connect Gmail/)).toBeInTheDocument();
  });
});
