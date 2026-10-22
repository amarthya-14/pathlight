import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { upsertMock } = vi.hoisted(() => ({ upsertMock: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { upsertProfile: upsertMock } };
});

import type { ProfileOut } from "@/lib/types";
import { PlacementRulesCard } from "./PlacementRulesCard";
import { ToastProvider } from "./Toast";

const PROFILE = {
  id: "p1",
  user_id: "u1",
  cgpa: 8.5,
  branch: "CSE",
  target_roles: ["SDE"],
  preferred_locations: [],
  open_to_remote: true,
  expected_ctc_lpa: null,
  notice_period: null,
  autopilot_enabled: false,
  autopilot_min_match: 75,
} as unknown as ProfileOut;

describe("PlacementRulesCard", () => {
  it("saves the college's tiers and the offer held, keeping the rest of the profile", async () => {
    upsertMock.mockImplementation(async (body) => ({ ...PROFILE, ...body }));
    const onSaved = vi.fn();
    render(
      <ToastProvider>
        <PlacementRulesCard profile={PROFILE} onSaved={onSaved} />
      </ToastProvider>
    );
    fireEvent.change(screen.getByPlaceholderText("5.5"), { target: { value: "5.5" } });
    fireEvent.change(screen.getByPlaceholderText("10"), { target: { value: "10" } });
    fireEvent.change(screen.getByPlaceholderText("Infosys"), { target: { value: "Infosys" } });
    fireEvent.change(screen.getByPlaceholderText("7"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: /Save rules/ }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = upsertMock.mock.calls[0][0];
    expect(body.placement_policy).toEqual({ dream_min_lpa: 5.5, super_dream_min_lpa: 10, after_offer: "higher_tier" });
    expect(body.current_offer).toEqual({ company: "Infosys", ctc_lpa: 7 });
    expect(body.cgpa).toBe(8.5);
    expect(body.target_roles).toEqual(["SDE"]);
  });
});
