import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { kitMock } = vi.hoisted(() => ({ kitMock: vi.fn() }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { applicationKit: kitMock } };
});

import { ApplicationKitPanel } from "./ApplicationKit";

describe("ApplicationKitPanel", () => {
  it("shows honest answers with their reasoning, and the referral helper", async () => {
    kitMock.mockResolvedValue({
      answers: [
        { question: "How many years of work experience do you have?", answer: "0", note: "Forms mean full-time experience." },
        { question: "How many years of experience do you have with Kafka?", answer: "0", note: "Kafka isn't on your resume." },
      ],
      connection_note: "Hi! I'm Asha, applying for SDE at Acme.",
      referral_message: "Hi {name}, ...",
      search_links: [{ label: "JNTU alumni at Acme", url: "https://www.linkedin.com/search/results/people/?keywords=Acme+JNTU" }],
    });
    render(<ApplicationKitPanel applicationId="a1" site="LinkedIn" />);

    expect(await screen.findByText("Kafka isn't on your resume.")).toBeInTheDocument();
    expect(screen.getByText("Forms mean full-time experience.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Ask for a referral/ }));
    expect(screen.getByRole("link", { name: /JNTU alumni at Acme/ })).toHaveAttribute("href", expect.stringContaining("linkedin.com"));
    expect(screen.getByText(/\d+\/300/)).toBeInTheDocument();
  });
});
