import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { pushMock, replaceMock, loginMock, refreshMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
  loginMock: vi.fn(),
  refreshMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { login: loginMock } };
});

let mockUser: { id: string; email: string; full_name: string | null } | null = null;
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: mockUser, loading: false, refresh: refreshMock, logout: vi.fn() }),
}));

import { ApiError } from "@/lib/api";
import LoginPage from "./page";

describe("LoginPage", () => {
  beforeEach(() => {
    loginMock.mockReset();
    refreshMock.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
    mockUser = null;
  });

  it("submits the entered credentials and navigates home on success", async () => {
    loginMock.mockResolvedValue({ access_token: "tok", token_type: "bearer" });
    refreshMock.mockResolvedValue(undefined);

    const { container } = render(<LoginPage />);

    fireEvent.change(container.querySelector("input[type=email]")!, {
      target: { value: "student@example.com" },
    });
    fireEvent.change(container.querySelector("input[type=password]")!, {
      target: { value: "supersecret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Log in/ }));

    await waitFor(() => expect(loginMock).toHaveBeenCalledWith("student@example.com", "supersecret"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
  });

  it("shows the ApiError detail message when login fails", async () => {
    loginMock.mockRejectedValue(new ApiError(401, "Incorrect email or password"));

    const { container } = render(<LoginPage />);

    fireEvent.change(container.querySelector("input[type=email]")!, {
      target: { value: "student@example.com" },
    });
    fireEvent.change(container.querySelector("input[type=password]")!, {
      target: { value: "wrongpass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Log in/ }));

    expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("redirects home immediately when already authenticated", () => {
    mockUser = { id: "1", email: "student@example.com", full_name: null };
    render(<LoginPage />);
    expect(replaceMock).toHaveBeenCalledWith("/");
  });
});
