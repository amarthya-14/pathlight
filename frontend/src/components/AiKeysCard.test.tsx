import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { addMock, setUserMock, authState } = vi.hoisted(() => ({
  addMock: vi.fn(),
  setUserMock: vi.fn(),
  authState: { user: { id: "1", email: "a@b.com", full_name: "Asha", ai_keys: [] as unknown[] } },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { addAiKey: addMock, removeAiKey: vi.fn(), reorderAiKeys: vi.fn() } };
});
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: authState.user, setUser: setUserMock }) }));

import { ToastProvider } from "./Toast";
import { AiKeysCard } from "./AiKeysCard";

const renderCard = () => render(<ToastProvider><AiKeysCard /></ToastProvider>);

describe("AiKeysCard", () => {
  beforeEach(() => {
    addMock.mockReset();
    setUserMock.mockReset();
  });

  it("guides the student through Google AI Studio and connects the key", async () => {
    addMock.mockResolvedValue({
      ai_keys: [{ provider: "gemini", last4: "abcd", strong_model: "g-strong", small_model: "g-small", base_url: null, added_at: "2026-10-03" }],
      message: "Google Gemini connected",
    });
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: /Add a key/ }));
    expect(screen.getByRole("radio", { name: /Google Gemini/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("link", { name: /Open Google AI Studio/ })).toHaveAttribute("href", "https://aistudio.google.com/apikey");

    fireEvent.change(screen.getByLabelText(/Google Gemini API key/), { target: { value: "AIzaSyTestKey" } });
    fireEvent.click(screen.getByRole("button", { name: /^Connect$/ }));

    await waitFor(() => expect(addMock).toHaveBeenCalledWith({ provider: "gemini", api_key: "AIzaSyTestKey", base_url: null, model: null }));
    await waitFor(() => expect(setUserMock).toHaveBeenCalled());
  });

  it("asks for a base URL and model for other OpenAI-compatible providers", () => {
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: /Add a key/ }));
    fireEvent.click(screen.getByRole("radio", { name: /Other/ }));
    expect(screen.getByLabelText("Base URL")).toBeRequired();
    expect(screen.getByLabelText("Model")).toBeRequired();
  });
});
