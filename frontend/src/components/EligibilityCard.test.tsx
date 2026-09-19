import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EligibilityCard } from "./EligibilityCard";
import type { EligibilityResult } from "@/lib/types";

function makeResult(overrides: Partial<EligibilityResult> = {}): EligibilityResult {
  return {
    decision: "eligible",
    reason: "All criteria met.",
    evidence: [],
    missing_information: [],
    confidence: 0.9,
    ...overrides,
  };
}

describe("EligibilityCard", () => {
  it("renders the eligible badge and reason", () => {
    render(<EligibilityCard eligibility={makeResult()} />);
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(screen.getByText("All criteria met.")).toBeInTheDocument();
  });

  it("renders evidence and missing information lists when present", () => {
    render(
      <EligibilityCard
        eligibility={makeResult({
          decision: "uncertain",
          evidence: ["CGPA requirement met: 8.5 >= 7"],
          missing_information: ["Profile branch is not set"],
        })}
      />
    );
    expect(screen.getByText("Uncertain")).toBeInTheDocument();
    expect(screen.getByText("CGPA requirement met: 8.5 >= 7")).toBeInTheDocument();
    expect(screen.getByText("Profile branch is not set")).toBeInTheDocument();
  });

  it.each([
    ["eligible", "Eligible"],
    ["partially_eligible", "Partially Eligible"],
    ["not_eligible", "Not Eligible"],
    ["uncertain", "Uncertain"],
  ] as const)("maps decision %s to label %s", (decision, label) => {
    render(<EligibilityCard eligibility={makeResult({ decision })} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
