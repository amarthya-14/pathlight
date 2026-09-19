import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SkillGapCard } from "./SkillGapCard";
import type { SkillGapResult } from "@/lib/types";

function makeResult(overrides: Partial<SkillGapResult> = {}): SkillGapResult {
  return {
    matched: [],
    weak: [],
    missing: [],
    github_evidence: {},
    github_unavailable: false,
    ...overrides,
  };
}

describe("SkillGapCard", () => {
  it("renders matched, weak, and missing skill pills", () => {
    render(
      <SkillGapCard
        skillGap={makeResult({ matched: ["Python"], weak: ["Docker"], missing: ["Kubernetes"] })}
      />
    );
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("shows an empty state when there are no skills to compare", () => {
    render(<SkillGapCard skillGap={makeResult()} />);
    expect(screen.getByText("No skills to compare.")).toBeInTheDocument();
  });

  it("renders the skillGapNote prominently when present", () => {
    render(<SkillGapCard skillGap={makeResult()} skillGapNote="No resume on file." />);
    expect(screen.getByText("No resume on file.")).toBeInTheDocument();
  });

  it("renders GitHub evidence when present", () => {
    render(
      <SkillGapCard
        skillGap={makeResult({ weak: ["Rust"], github_evidence: { Rust: ["my-rust-project (Rust)"] } })}
      />
    );
    expect(screen.getByText("GitHub evidence")).toBeInTheDocument();
    expect(screen.getByText("my-rust-project (Rust)")).toBeInTheDocument();
  });

  it("notes when GitHub evidence lookup was unavailable", () => {
    render(<SkillGapCard skillGap={makeResult({ missing: ["Swift"], github_unavailable: true })} />);
    expect(screen.getByText(/GitHub evidence lookup was unavailable/)).toBeInTheDocument();
  });
});
