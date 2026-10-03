import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { reviewMock, downloadMock, markAppliedMock, saveBlobMock, editMock } = vi.hoisted(() => ({
  editMock: vi.fn(),
  reviewMock: vi.fn(),
  downloadMock: vi.fn(),
  markAppliedMock: vi.fn(),
  saveBlobMock: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    saveBlob: saveBlobMock,
    api: { reviewApplication: reviewMock, downloadTailoredResumePdf: downloadMock, markApplied: markAppliedMock, editTailoredResume: editMock },
  };
});

import { ApiError } from "@/lib/api";
import type { ApplicationOut, TailoredResumeOut } from "@/lib/types";
import { applySiteLabel, FinishApplyPanel, ReviewApplyCard } from "./ReviewApplyCard";

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
    min_experience_years: null,
    has_job_description: false,
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
  ats: null,
  generated_at: "2026-10-01T00:00:00Z",
};

describe("ReviewApplyCard", () => {
  beforeEach(() => {
    // Block body on purpose: a function returned from beforeEach is run as a teardown
    // hook, and mockReset() returns the mock itself.
    reviewMock.mockReset();
    downloadMock.mockReset();
    markAppliedMock.mockReset();
    saveBlobMock.mockReset();
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

  it("one click on 'Apply on LinkedIn' opens the job, copies the cover note, downloads the PDF, and records approval", async () => {
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const blob = new Blob(["%PDF"]);
    downloadMock.mockResolvedValue({ blob, filename: "Resume.pdf" });
    reviewMock.mockResolvedValue({ outcome: "manual_apply_required" });
    const onReviewed = vi.fn();
    const url = "https://www.linkedin.com/jobs/view/42";

    render(
      <ReviewApplyCard
        application={makeApp({ apply_email: null, application_url: url })}
        tailored={TAILORED}
        onReviewed={onReviewed}
      />
    );
    fireEvent.click(screen.getByText("Apply on LinkedIn"));

    expect(openSpy).toHaveBeenCalledWith(url, "_blank", "noopener,noreferrer");
    expect(writeText).toHaveBeenCalledWith("Dear Hiring Team, hello.");
    await waitFor(() => expect(onReviewed).toHaveBeenCalled());
    expect(saveBlobMock).toHaveBeenCalledWith(blob, "Resume.pdf");
    expect(reviewMock).toHaveBeenCalledWith("app1", true);
    openSpy.mockRestore();
  });
});

describe("applySiteLabel", () => {
  it("names well-known job sites", () => {
    expect(applySiteLabel("https://www.linkedin.com/comm/jobs/view/1")).toBe("LinkedIn");
    expect(applySiteLabel("https://www.naukri.com/job-listings-x")).toBe("Naukri");
    expect(applySiteLabel("https://careers.acme.dev/jobs/1")).toBe("careers.acme.dev");
    expect(applySiteLabel(null)).toBe("the posting site");
  });
});

describe("FinishApplyPanel", () => {
  beforeEach(() => {
    markAppliedMock.mockReset();
  });

  it("marks the application applied only when the user confirms", async () => {
    const onMarked = vi.fn();
    markAppliedMock.mockResolvedValue({ id: "app1" });
    render(
      <FinishApplyPanel
        application={makeApp({ apply_email: null, application_url: "https://www.linkedin.com/jobs/view/42" })}
        tailored={TAILORED}
        onMarked={onMarked}
      />
    );
    expect(markAppliedMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("I've submitted it on LinkedIn"));
    await waitFor(() => expect(onMarked).toHaveBeenCalledWith({ id: "app1" }));
  });

  it("shows the ATS score and names the skills that cap it instead of claiming them", () => {
    const ats = {
      score: 94,
      breakdown: { keywords: 39, job_title: 5, sections: 15, contact: 10, format: 15, impact: 10 },
      matched_keywords: ["Java"],
      fixable_keywords: [],
      missing_keywords: ["Kafka", "Microservices"],
      blocked_points: 6,
      suggestions: [],
    };
    render(<ReviewApplyCard application={makeApp()} tailored={{ ...TAILORED, ats }} onReviewed={() => {}} />);

    expect(screen.getByText("Best honest score")).toBeInTheDocument();
    expect(screen.getByText(/6 points need skills that aren.t on your resume/)).toBeInTheDocument();
    expect(screen.getByText(/Kafka, Microservices/)).toBeInTheDocument();
  });

  it("lets the student edit the tailored resume and shows the re-scored result", async () => {
    const onChange = vi.fn();
    editMock.mockResolvedValue({ ...TAILORED, tailored_text: "Name\nSkills: Python, Django" });
    render(<ReviewApplyCard application={makeApp()} tailored={TAILORED} onReviewed={() => {}} onTailoredChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /Edit/ }));
    fireEvent.change(screen.getByLabelText("Tailored resume"), { target: { value: "Name\nSkills: Python, Django" } });
    fireEvent.click(screen.getByRole("button", { name: /Save edits/ }));

    await waitFor(() => expect(editMock).toHaveBeenCalledWith("app1", "Name\nSkills: Python, Django", TAILORED.cover_note));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });
});
