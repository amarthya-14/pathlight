import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { pushMock, replaceMock, registerMock, loginMock, refreshMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
  registerMock: vi.fn(),
  loginMock: vi.fn(),
  refreshMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { register: registerMock, login: loginMock } };
});

let mockUser: { id: string; email: string; full_name: string | null } | null = null;
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: mockUser, loading: false, refresh: refreshMock, logout: vi.fn() }),
}));

import { ApiError } from "@/lib/api";
import RegisterPage from "./page";

describe("RegisterPage", () => {
  beforeEach(() => {
    registerMock.mockReset();
    loginMock.mockReset();
    refreshMock.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
    mockUser = null;
  });

  it("registers, logs in, and navigates home on success", async () => {
    registerMock.mockResolvedValue({ id: "1", email: "student@example.com", full_name: null });
    loginMock.mockResolvedValue({ access_token: "tok", token_type: "bearer" });
    refreshMock.mockResolvedValue(undefined);

    const { container } = render(<RegisterPage />);

    fireEvent.change(container.querySelector("input[type=email]")!, {
      target: { value: "student@example.com" },
    });
    fireEvent.change(container.querySelector("input[type=password]")!, {
      target: { value: "supersecret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Register/ }));

    await waitFor(() => expect(registerMock).toHaveBeenCalledWith("student@example.com", "supersecret"));
    await waitFor(() => expect(loginMock).toHaveBeenCalledWith("student@example.com", "supersecret"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
  });

  it("shows the ApiError detail message when registration fails (e.g. duplicate email)", async () => {
    registerMock.mockRejectedValue(new ApiError(409, "Email already registered"));

    const { container } = render(<RegisterPage />);

    fireEvent.change(container.querySelector("input[type=email]")!, {
      target: { value: "student@example.com" },
    });
    fireEvent.change(container.querySelector("input[type=password]")!, {
      target: { value: "supersecret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Register/ }));

    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("redirects home immediately when already authenticated", () => {
    mockUser = { id: "1", email: "student@example.com", full_name: null };
    render(<RegisterPage />);
    expect(replaceMock).toHaveBeenCalledWith("/");
  });
});
