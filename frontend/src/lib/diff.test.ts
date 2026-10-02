import { describe, expect, it } from "vitest";
import { diffLines } from "./diff";

describe("diffLines", () => {
  it("marks identical text as unchanged", () => {
    expect(diffLines("a\nb", "a\nb")).toEqual([
      { type: "same", text: "a" },
      { type: "same", text: "b" },
    ]);
  });

  it("detects a reworded line as removed + added", () => {
    const result = diffLines("Name\nSkills: Python\nEnd", "Name\nSkills: Python (primary)\nEnd");
    expect(result).toEqual([
      { type: "same", text: "Name" },
      { type: "removed", text: "Skills: Python" },
      { type: "added", text: "Skills: Python (primary)" },
      { type: "same", text: "End" },
    ]);
  });

  it("detects reordered sections", () => {
    const result = diffLines("A\nB\nC", "C\nA\nB");
    expect(result.filter((l) => l.type === "same").map((l) => l.text)).toEqual(["A", "B"]);
    expect(result.filter((l) => l.type !== "same")).toHaveLength(2);
  });

  it("normalizes CRLF line endings", () => {
    expect(diffLines("a\r\nb", "a\nb").every((l) => l.type === "same")).toBe(true);
  });
});
