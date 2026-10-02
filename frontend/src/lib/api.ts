import type {
  ApplicationOut,
  DashboardHomeOut,
  DocumentDetailOut,
  DocumentOut,
  GmailSyncOut,
  IngestResponse,
  IntegrationOut,
  PreparationPlanOut,
  ProfileOut,
  ProfileUpsert,
  ReviewResponse,
  TailoredResumeOut,
  UserOut,
} from "./types";
import { ApiError } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "pathlight_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; formBody?: string; multipart?: FormData; auth?: boolean } = {}
): Promise<T> {
  const { method = "GET", body, formBody, multipart, auth = true } = options;
  const headers: Record<string, string> = {};

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let requestBody: string | FormData | undefined;
  if (multipart !== undefined) {
    // No Content-Type header: the browser sets multipart/form-data with the boundary.
    requestBody = multipart;
  } else if (formBody !== undefined) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    requestBody = formBody;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: requestBody });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      detail = errBody.detail ?? detail;
    } catch {
      // response body wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function requestFile(path: string): Promise<{ blob: Blob; filename: string }> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, res.statusText || "Download failed");
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "resume.pdf";
  return { blob: await res.blob(), filename };
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  register: (email: string, password: string) =>
    request<UserOut>("/api/auth/register", { method: "POST", body: { email, password }, auth: false }),

  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password }).toString();
    const result = await request<{ access_token: string; token_type: string }>("/api/auth/login", {
      method: "POST",
      formBody: body,
      auth: false,
    });
    setToken(result.access_token);
    return result;
  },

  me: () => request<UserOut>("/api/auth/me"),

  getProfile: () => request<ProfileOut>("/api/profile"),
  upsertProfile: (payload: ProfileUpsert) => request<ProfileOut>("/api/profile", { method: "PUT", body: payload }),

  listDocuments: () => request<DocumentOut[]>("/api/documents"),
  pasteDocument: (payload: { doc_type: string; title: string; text: string }) =>
    request<DocumentOut>("/api/documents/paste", { method: "POST", body: payload }),
  uploadDocument: (file: File, docType: string) => {
    const form = new FormData();
    form.append("doc_type", docType);
    form.append("file", file);
    return request<DocumentDetailOut>("/api/documents/upload", { method: "POST", multipart: form });
  },

  ingestOpportunity: (payload: { raw_text: string; source?: string }) =>
    request<IngestResponse>("/api/opportunities/ingest", { method: "POST", body: payload }),

  listApplications: () => request<ApplicationOut[]>("/api/applications"),
  getApplication: (id: string) => request<ApplicationOut>(`/api/applications/${id}`),

  getPreparationPlan: (applicationId: string) =>
    request<PreparationPlanOut>(`/api/applications/${applicationId}/preparation-plan`),
  regeneratePreparationPlan: (applicationId: string, hoursPerDay: number) =>
    request<PreparationPlanOut>(`/api/applications/${applicationId}/preparation-plan`, {
      method: "POST",
      body: { hours_per_day: hoursPerDay },
    }),

  getDashboardHome: () => request<DashboardHomeOut>("/api/dashboard/home"),

  getTailoredResume: (applicationId: string) =>
    request<TailoredResumeOut>(`/api/applications/${applicationId}/tailored-resume`),
  tailorApplication: (applicationId: string) =>
    request<TailoredResumeOut>(`/api/applications/${applicationId}/tailor`, { method: "POST" }),
  downloadTailoredResumePdf: (applicationId: string) =>
    requestFile(`/api/applications/${applicationId}/tailored-resume.pdf`),
  markApplied: (applicationId: string) =>
    request<ApplicationOut>(`/api/applications/${applicationId}/mark-applied`, { method: "POST" }),
  reviewApplication: (applicationId: string, approve: boolean) =>
    request<ReviewResponse>(`/api/applications/${applicationId}/review`, { method: "POST", body: { approve } }),

  listIntegrations: () => request<IntegrationOut[]>("/api/integrations"),
  gmailConnectUrl: () => request<{ auth_url: string }>("/api/integrations/gmail/connect"),
  disconnectGmail: () => request<void>("/api/integrations/gmail", { method: "DELETE" }),
  syncGmail: () => request<GmailSyncOut>("/api/integrations/gmail/sync", { method: "POST" }),
};

export { ApiError };
