"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, Inbox, Lock, Mail, RefreshCw, Send, ShieldCheck, TriangleAlert, Unplug } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { GmailSyncOut, GmailSyncStatus, IntegrationOut } from "@/lib/types";
import { Alert, Badge, Button, buttonClasses, Card, PageHeader, Skeleton } from "@/components/ui";

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
  const [syncing, setSyncing] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // "Check now" runs on the server in the background (every job in every alert goes
  // through the full pipeline — minutes, not seconds). Poll its status until it settles.
  const followSync = useCallback((status: GmailSyncStatus) => {
    if (pollTimer.current) clearTimeout(pollTimer.current);
    if (status.state === "running") {
      setSyncing(true);
      pollTimer.current = setTimeout(() => {
        api.gmailSyncStatus().then(followSync).catch(() => setSyncing(false));
      }, 3000);
      return;
    }
    setSyncing(false);
    if (status.state === "done" && status.result) setSyncResult(status.result);
    if (status.state === "error") setError(status.error ? `Check failed: ${status.error}` : "The inbox check failed.");
  }, []);

  useEffect(() => () => {
    if (pollTimer.current) clearTimeout(pollTimer.current);
  }, []);

  const load = useCallback(() => {
    api
      .listIntegrations()
      .then((list) => {
        setIntegrations(list);
        // Pick up a check that's still running from before a reload.
        if (list.some((i) => i.provider === "gmail" && i.status === "connected")) {
          api.gmailSyncStatus().then((s) => s.state === "running" && followSync(s)).catch(() => {});
        }
      })
      .catch(() => setIntegrations([]));
  }, [followSync]);

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
      setSyncResult(null);
      followSync(await api.syncGmail());
    });

  // Refresh "last checked" once a background check finishes.
  useEffect(() => {
    if (!syncing && syncResult) load();
  }, [syncing, syncResult, load]);

  const onDisconnect = () =>
    run("disconnect", async () => {
      await api.disconnectGmail();
      setSyncResult(null);
      setMessage("Gmail disconnected and access revoked with Google.");
      load();
    });

  if (authLoading || !user) return null;

  const connected = gmail?.status === "connected";

  return (
    <div className="max-w-4xl space-y-6">
      <div className="animate-fade-in">
        <PageHeader
          title="Integrations"
          subtitle="Let opportunities come to you. Pathlight watches your job alerts, prepares each application, and applies only after you approve."
        />
      </div>

      {message && <Alert tone="ok">{message}</Alert>}
      {error && <Alert tone="bad">{error}</Alert>}

      {integrations === null ? (
        <Skeleton className="h-56" />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6">
            <div className="flex items-start gap-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-2">
                <Mail size={20} className="text-fg" strokeWidth={1.8} />
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-[15px] font-semibold text-fg">Gmail</h2>
                  {connected && <Badge tone="ok" dot>Connected</Badge>}
                  {gmail?.status === "error" && <Badge tone="bad" icon={TriangleAlert}>Needs reconnecting</Badge>}
                </div>
                <p className="mt-1 max-w-lg text-[13px] leading-relaxed text-muted">
                  {connected && gmail?.account_email ? (
                    <>
                      Watching <span className="font-medium text-fg">{gmail.account_email}</span> for LinkedIn and Naukri job alerts.
                    </>
                  ) : (
                    "Reads LinkedIn and Naukri job-alert emails, tailors your resume for each role and — after you approve — sends the application from your account."
                  )}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {!connected && (
                <Button onClick={onConnect} loading={busy === "connect"}>
                  {busy === "connect" ? "Redirecting to Google…" : gmail ? "Reconnect Gmail" : "Connect Gmail"}
                </Button>
              )}
              {connected && (
                <Button variant="secondary" onClick={onSync} loading={busy === "sync" || syncing} disabled={busy !== null || syncing}>
                  {busy !== "sync" && !syncing && <RefreshCw size={13} />}
                  {syncing ? "Checking inbox…" : "Check now"}
                </Button>
              )}
              {gmail && (
                <Button variant="ghost" onClick={onDisconnect} loading={busy === "disconnect"} disabled={busy !== null}>
                  {busy !== "disconnect" && <Unplug size={13} />} Disconnect
                </Button>
              )}
            </div>
          </div>

          {gmail && (
            <dl className="grid grid-cols-2 border-t border-line text-[13px] sm:grid-cols-3">
              <div className="border-r border-line px-5 py-3.5 sm:px-6">
                <dt className="text-xs text-subtle">Connected</dt>
                <dd className="mt-0.5 font-medium text-fg">{new Date(gmail.connected_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</dd>
              </div>
              <div className="px-5 py-3.5 sm:border-r sm:border-line sm:px-6">
                <dt className="text-xs text-subtle">Last checked</dt>
                <dd className="mt-0.5 font-medium text-fg">
                  {gmail.last_polled_at ? new Date(gmail.last_polled_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "Not yet"}
                </dd>
              </div>
              <div className="col-span-2 border-t border-line px-5 py-3.5 sm:col-span-1 sm:border-t-0 sm:px-6">
                <dt className="text-xs text-subtle">Permissions</dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {gmail.scopes.some((sc) => sc.endsWith("gmail.readonly")) && <Badge>Read alerts</Badge>}
                  {gmail.scopes.some((sc) => sc.endsWith("gmail.send")) && <Badge>Send on approval</Badge>}
                </dd>
              </div>
            </dl>
          )}

          {syncing && (
            <div className="sweep flex items-center gap-2.5 border-t border-line bg-surface-2 px-5 py-3.5 text-[13px] text-muted sm:px-6">
              <Inbox size={15} className="shrink-0" />
              Reading new job alerts and preparing each role — this runs on the server, so you can leave this page.
            </div>
          )}

          {gmail?.last_error && (
            <div className="border-t border-line px-5 py-3 sm:px-6">
              <Alert tone="bad">{gmail.last_error}</Alert>
            </div>
          )}

          {syncResult && (
            <div className="animate-fade-in flex flex-col gap-3 border-t border-line bg-surface-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div className="flex items-center gap-2.5 text-[13px] text-fg">
                <Inbox size={15} className="shrink-0 text-muted" />
                <span>
                  Checked {syncResult.messages_seen} alert email{syncResult.messages_seen === 1 ? "" : "s"} —{" "}
                  <strong>
                    {syncResult.opportunities_ingested} new opportunit{syncResult.opportunities_ingested === 1 ? "y" : "ies"}
                  </strong>
                  {syncResult.skipped_already_processed > 0 && `, ${syncResult.skipped_already_processed} already seen`}
                  {syncResult.skipped_not_relevant > 0 && `, ${syncResult.skipped_not_relevant} skipped (senior or outside your field)`}.
                  {syncResult.failures.length > 0 && <span className="text-warn"> {syncResult.failures.length} couldn&apos;t be processed.</span>}
                </span>
              </div>
              {syncResult.opportunities_ingested > 0 && (
                <Link href="/applications" className={buttonClasses("primary", "sm", "shrink-0")}>
                  Review them <ArrowRight size={12} />
                </Link>
              )}
            </div>
          )}
        </Card>
      )}

      <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3">
        {[
          { icon: ShieldCheck, title: "Alerts only", text: "Only mail from LinkedIn and Naukri job-alert senders is ever read — never the rest of your inbox." },
          { icon: Send, title: "Never sends alone", text: "An application is only sent after you review it and explicitly approve." },
          { icon: Lock, title: "Encrypted and revocable", text: "Access tokens are encrypted at rest. Disconnecting revokes them with Google." },
        ].map(({ icon: Icon, title, text }) => (
          <div key={title} className="bg-surface p-5">
            <Icon size={16} className="text-fg" strokeWidth={1.8} />
            <div className="mt-3 text-[13px] font-semibold text-fg">{title}</div>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{text}</p>
          </div>
        ))}
      </div>

      {connected && (
        <p className="flex items-center gap-2 text-xs text-subtle">
          <Check size={13} className="text-ok" /> New alerts are checked automatically once a day (around 9 AM). Use “Check now” any time.
        </p>
      )}
    </div>
  );
}
