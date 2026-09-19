import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBar } from "./ConfidenceBar";

describe("ConfidenceBar", () => {
  it("rounds a fractional confidence to a whole percentage", () => {
    render(<ConfidenceBar confidence={0.876} />);
    expect(screen.getByText("88% confidence")).toBeInTheDocument();
  });

  it("clamps values above 1 to 100%", () => {
    render(<ConfidenceBar confidence={1.5} />);
    expect(screen.getByText("100% confidence")).toBeInTheDocument();
  });

  it("clamps negative values to 0%", () => {
    render(<ConfidenceBar confidence={-0.2} />);
    expect(screen.getByText("0% confidence")).toBeInTheDocument();
  });
});
