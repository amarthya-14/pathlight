import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusTimeline } from "./StatusTimeline";
import type { ApplicationStatusEvent } from "@/lib/types";

describe("StatusTimeline", () => {
  it("shows an empty-state message when there is no history", () => {
    render(<StatusTimeline history={[]} />);
    expect(screen.getByText("No status history yet.")).toBeInTheDocument();
  });

  it("renders each event's mapped stage label and note", () => {
    const history: ApplicationStatusEvent[] = [
      { stage: "DISCOVERED", note: null, created_at: "2026-01-01T00:00:00Z" },
      { stage: "APPLIED", note: "Submitted via portal", created_at: "2026-01-05T00:00:00Z" },
    ];
    render(<StatusTimeline history={history} />);

    expect(screen.getByText("Discovered")).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(screen.getByText("Submitted via portal")).toBeInTheDocument();
  });

  it("falls back to the raw stage string for an unmapped stage", () => {
    const history = [
      { stage: "SOMETHING_NEW", note: null, created_at: "2026-01-01T00:00:00Z" },
    ] as unknown as ApplicationStatusEvent[];
    render(<StatusTimeline history={history} />);
    expect(screen.getByText("SOMETHING_NEW")).toBeInTheDocument();
  });
});
