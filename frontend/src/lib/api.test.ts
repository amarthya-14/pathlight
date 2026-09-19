import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, clearToken, getToken, setToken } from "./api";

describe("token storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("round-trips a token through set/get/clear", () => {
    setToken("abc123");
    expect(getToken()).toBe("abc123");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("api.request", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a JSON body and returns the parsed response on success", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "1", email: "a@b.com", full_name: null }),
    });

    const result = await api.register("a@b.com", "password123");

    expect(result).toEqual({ id: "1", email: "a@b.com", full_name: null });
    const [url, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/auth/register");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ email: "a@b.com", password: "password123" });
  });

  it("attaches the Authorization header when a token is present and auth is required", async () => {
    setToken("my-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "1", email: "a@b.com", full_name: null }),
    });

    await api.me();

    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers["Authorization"]).toBe("Bearer my-token");
  });

  it("does not attach an Authorization header for unauthenticated endpoints", async () => {
    setToken("my-token");
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "1", email: "a@b.com", full_name: null }),
    });

    await api.register("a@b.com", "password123");

    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers["Authorization"]).toBeUndefined();
  });

  it("throws ApiError with the response detail on a non-OK response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: async () => ({ detail: "Email already registered" }),
    });

    await expect(api.register("a@b.com", "password123")).rejects.toMatchObject({
      status: 409,
      detail: "Email already registered",
    } satisfies Partial<ApiError>);
  });

  it("falls back to statusText when the error response isn't JSON", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });

    await expect(api.register("a@b.com", "password123")).rejects.toMatchObject({
      status: 500,
      detail: "Internal Server Error",
    });
  });

  it("sends login credentials as a form-encoded body and stores the returned token", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "new-token", token_type: "bearer" }),
    });

    await api.login("a@b.com", "password123");

    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");
    expect(options.body).toBe("username=a%40b.com&password=password123");
    expect(getToken()).toBe("new-token");
  });
});
