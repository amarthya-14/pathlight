import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { addressMock } = vi.hoisted(() => ({ addressMock: vi.fn() }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { alertAddress: addressMock, rotateAlertAddress: vi.fn() } };
});

import { ALERT_FROM, AlertForwardingCard } from "./AlertForwarding";

describe("AlertForwardingCard", () => {
  it("shows the private address, the setup steps and Gmail's confirmation code", async () => {
    addressMock.mockResolvedValue({
      enabled: true,
      address: "k7x2m9qabc@alerts.example.com",
      activity: [
        {
          kind: "gmail_confirmation", status: "done", subject: null, jobs_ingested: 0, skipped_not_relevant: 0, error: null,
          confirmation_code: "123456789", confirmation_link: "https://mail-settings.google.com/mail/vf-x", received_at: new Date().toISOString(),
        },
      ],
    });
    render(<AlertForwardingCard />);

    expect(await screen.findByText("k7x2m9qabc@alerts.example.com")).toBeInTheDocument();
    expect(screen.getByText("Gmail sent your confirmation code")).toBeInTheDocument();
    expect(screen.getByText("123456789")).toBeInTheDocument();
    expect(screen.getByText(ALERT_FROM)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open link/ })).toHaveAttribute("href", "https://mail-settings.google.com/mail/vf-x");
  });

  it("says coming soon when the server hasn't set forwarding up", async () => {
    addressMock.mockResolvedValue({ enabled: false, address: null, activity: [] });
    render(<AlertForwardingCard />);
    expect(await screen.findByText("Coming soon")).toBeInTheDocument();
  });
});
