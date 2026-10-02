"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Mail, RefreshCw, ShieldCheck, TriangleAlert, Unplug } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { GmailSyncOut, IntegrationOut } from "@/lib/types";
import { Button, PageHeader, SectionLabel } from "@/components/ui";

const CALLBACK_ERRORS: Record<string, string> = {
  access_denied: "You declined Gmail access — nothing was connected.",
  invalid_state: "The connection link expired or was invalid. Please try again.",
  token_exchange_failed: "Google didn't complete the connection. Please try again.",
};

export default function IntegrationsPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [integrations, setIntegrations] = useState<IntegrationOut[] | null>(null);
  const [busy, setBusy] = useState<"connect" | "sync" | "disconnect" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<GmailSyncOut | null>(null);

  const load = useCallback(() => {
    api
      .listIntegrations()
      .then(setIntegrations)
      .catch(() => setIntegrations([]));
  }, []);

  useEffect(() => {
    if (!user) return;
    load();
    // Read the OAuth callback's ?gmail=… result directly (client-only page — avoids
    // useSearchParams' Suspense requirement), then strip it so a refresh doesn't re-show it.
    const params = new URLSearchParams(window.location.search);
    const result = params.get("gmail");
    if (result === "connected") setMessage("Gmail connected. Pathlight will now watch your job-alert emails.");
    if (result === "error") setError(CALLBACK_ERRORS[params.get("reason") ?? ""] ?? "Gmail connection failed.");
    if (result) window.history.replaceState(null, "", window.location.pathname);
  }, [user, load]);

  const gmail = integrations?.find((i) => i.provider === "gmail") ?? null;

  const run = async (kind: "connect" | "sync" | "disconnect", fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong");
    } finally {
      setBusy(null);
    }
  };

  const onConnect = () =>
    run("connect", async () => {
      const { auth_url } = await api.gmailConnectUrl();
      window.location.assign(auth_url);
    });

  const onSync = () =>
    run("sync", async () => {
      const result = await api.syncGmail();
      setSyncResult(result);
      load();
    });

  const onDisconnect = () =>
    run("disconnect", async () => {
      await api.disconnectGmail();
      setSyncResult(null);
      setMessage("Gmail disconnected and access revoked with Google.");
      load();
    });

  if (authLoading || !user) return null;

  return (
    <div className="animate-fade-in max-w-2xl space-y-10">
      <PageHeader
        title="Integrations"
        subtitle="Let Pathlight find off-campus openings for you and apply — only after you approve each one."
      />

      <section>
        <SectionLabel>Gmail</SectionLabel>
        <div className="card-shadow space-y-5 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-500">
              <Mail size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                Gmail
                {gmail?.status === "connected" && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                    <CheckCircle2 size={12} /> Connected{gmail.account_email ? ` · ${gmail.account_email}` : ""}
                  </span>
                )}
                {gmail?.status === "error" && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                    <TriangleAlert size={12} /> Needs reconnecting
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Reads LinkedIn and Naukri job-alert emails to discover openings, tailors your resume for each, and
                — after you approve — emails the application from your account.
              </p>
            </div>
          </div>

          <ul className="space-y-1.5 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <li className="flex gap-2">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-500" /> Only reads mail from job-alert
              senders — never the rest of your inbox.
            </li>
            <li className="flex gap-2">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-500" /> Never sends anything without your
              explicit approval on each application.
            </li>
            <li className="flex gap-2">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-500" /> Access tokens are encrypted at rest;
              disconnecting revokes them with Google.
            </li>
          </ul>

          {gmail && (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-slate-400">Connected</dt>
                <dd className="text-slate-700">{new Date(gmail.connected_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Last checked</dt>
                <dd className="text-slate-700">
                  {gmail.last_polled_at ? new Date(gmail.last_polled_at).toLocaleString() : "Not yet"}
                </dd>
              </div>
              {gmail.last_error && (
                <div className="col-span-2 text-rose-600">
                  <dt className="text-xs">Last error</dt>
                  <dd>{gmail.last_error}</dd>
                </div>
              )}
            </dl>
          )}

          <div className="flex flex-wrap gap-2">
            {gmail?.status !== "connected" && (
              <Button onClick={onConnect} disabled={busy !== null || integrations === null}>
                <Mail size={15} /> {busy === "connect" ? "Redirecting…" : gmail ? "Reconnect Gmail" : "Connect Gmail"}
              </Button>
            )}
            {gmail?.status === "connected" && (
              <Button onClick={onSync} disabled={busy !== null}>
                <RefreshCw size={15} className={busy === "sync" ? "animate-spin" : ""} />
                {busy === "sync" ? "Checking inbox…" : "Check for new alerts now"}
              </Button>
            )}
            {gmail && (
              <Button variant="secondary" onClick={onDisconnect} disabled={busy !== null}>
                <Unplug size={15} /> {busy === "disconnect" ? "Disconnecting…" : "Disconnect"}
              </Button>
            )}
          </div>

          {syncResult && (
            <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
              Checked {syncResult.messages_seen} alert email{syncResult.messages_seen === 1 ? "" : "s"} —{" "}
              <strong>{syncResult.opportunities_ingested}</strong> new opportunit
              {syncResult.opportunities_ingested === 1 ? "y" : "ies"} added
              {syncResult.skipped_already_processed > 0 && `, ${syncResult.skipped_already_processed} already seen`}.
              {syncResult.opportunities_ingested > 0 && " Open Applications to review tailored resumes."}
              {syncResult.failures.length > 0 && (
                <div className="mt-1 text-amber-700">{syncResult.failures.length} couldn&apos;t be processed.</div>
              )}
            </div>
          )}
        </div>
      </section>

      {message && <p className="text-sm font-medium text-emerald-600">{message}</p>}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </div>
  );
}
