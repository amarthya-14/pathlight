import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { replaceMock, apiMeMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  apiMeMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    api: { me: apiMeMock },
  };
});

import { getToken, setToken } from "./api";
import { AuthProvider, useAuth, useRequireAuth } from "./auth-context";

function Probe() {
  const { user, loading } = useAuth();
  return <div data-testid="probe">{loading ? "loading" : user ? `user:${user.email}` : "no-user"}</div>;
}

function RequireAuthProbe() {
  useRequireAuth();
  return <div>protected content</div>;
}

describe("AuthProvider / useAuth", () => {
  beforeEach(() => {
    window.localStorage.clear();
    apiMeMock.mockReset();
    replaceMock.mockReset();
  });

  it("resolves to no user when no token is stored, without calling the API", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("no-user"));
    expect(apiMeMock).not.toHaveBeenCalled();
  });

  it("sets the user when a token is present and api.me() succeeds", async () => {
    setToken("valid-token");
    apiMeMock.mockResolvedValue({ id: "1", email: "student@example.com", full_name: null });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("user:student@example.com"));
  });

  it("clears the token and user when api.me() rejects", async () => {
    setToken("stale-token");
    apiMeMock.mockRejectedValue(new Error("401"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("no-user"));
    expect(getToken()).toBeNull();
  });
});

describe("useRequireAuth", () => {
  beforeEach(() => {
    window.localStorage.clear();
    apiMeMock.mockReset();
    replaceMock.mockReset();
  });

  it("redirects to /login once loading settles with no user", async () => {
    render(
      <AuthProvider>
        <RequireAuthProbe />
      </AuthProvider>
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("does not redirect once a user is resolved", async () => {
    setToken("valid-token");
    apiMeMock.mockResolvedValue({ id: "1", email: "student@example.com", full_name: null });

    render(
      <AuthProvider>
        <RequireAuthProbe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("protected content")).toBeInTheDocument());
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
