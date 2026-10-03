import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { pushMock, listMock } = vi.hoisted(() => ({ pushMock: vi.fn(), listMock: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { listApplications: listMock } };
});

import { CommandPalette } from "./CommandPalette";

const APP = {
  id: "a1",
  opportunity_id: "o1",
  company_name: "Aptora Labs",
  role: "Spring Boot Developer",
  deadline: null,
  source: "gmail_mcp",
  apply_email: null,
  application_url: null,
  min_experience_years: null,
  has_job_description: false,
  eligibility: null,
  skill_gap: null,
  skill_gap_note: null,
  status_history: [{ stage: "READY_TO_APPLY", note: null, created_at: "2026-10-01T00:00:00Z" }],
  created_at: "2026-10-01T00:00:00Z",
};

describe("CommandPalette", () => {
  beforeEach(() => {
    pushMock.mockReset();
    listMock.mockReset();
    listMock.mockResolvedValue([APP]);
  });

  it("renders nothing when closed", () => {
    const { container } = render(<CommandPalette open={false} onClose={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("filters applications by query and opens the selected one with Enter", async () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />);
    await waitFor(() => expect(listMock).toHaveBeenCalled());

    const input = screen.getByPlaceholderText(/Search applications/);
    fireEvent.change(input, { target: { value: "spring" } });
    expect(await screen.findByText("Spring Boot Developer")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(pushMock).toHaveBeenCalledWith("/applications/a1");
    expect(onClose).toHaveBeenCalled();
  });

  it("navigates pages with the keyboard and closes on Escape", async () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />);
    const input = screen.getByPlaceholderText(/Search applications/);
    fireEvent.change(input, { target: { value: "profile" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(pushMock).toHaveBeenCalledWith("/profile");

    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
