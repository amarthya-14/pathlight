"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Inbox, Lock, Mail, RefreshCw, Send, ShieldCheck, TriangleAlert, Unplug } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { GmailSyncOut, IntegrationOut } from "@/lib/types";
import { Alert, Badge, Button, buttonClasses, Card, PageHeader, SectionLabel, Skeleton } from "@/components/ui";

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

  const connected = gmail?.status === "connected";

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <PageHeader
          eyebrow="Automate"
          title="Integrations"
          subtitle="Let opportunities come to you. Pathlight watches your job alerts, prepares each application, and applies only after you approve."
        />
      </div>

      {message && <Alert tone="ok">{message}</Alert>}
      {error && <Alert tone="bad">{error}</Alert>}

      {integrations === null ? (
        <Skeleton className="h-72" />
      ) : (
        <Card glow={connected} className="animate-fade-in relative overflow-hidden">
          <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-rose-500/10 blur-3xl" />
          <div className="relative p-5 sm:p-7">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-4">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 to-orange-400 text-white shadow-lg shadow-rose-500/25">
                  <Mail size={26} />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-fg">Gmail</h2>
                    {connected && (
                      <Badge tone="ok" dot>
                        Connected
                      </Badge>
                    )}
                    {gmail?.status === "error" && (
                      <Badge tone="bad" icon={TriangleAlert}>
                        Needs reconnecting
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 max-w-lg text-sm leading-relaxed text-muted">
                    {connected && gmail?.account_email ? (
                      <>
                        Watching <span className="font-medium text-fg">{gmail.account_email}</span> for LinkedIn & Naukri job
                        alerts.
                      </>
                    ) : (
                      "Reads LinkedIn and Naukri job-alert emails, tailors your resume for each role and — after you approve — sends the application from your account."
                    )}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 sm:justify-end">
                {!connected && (
                  <Button size="lg" onClick={onConnect} loading={busy === "connect"}>
                    {busy !== "connect" && <Mail size={16} />}
                    {busy === "connect" ? "Redirecting to Google…" : gmail ? "Reconnect Gmail" : "Connect Gmail"}
                  </Button>
                )}
                {connected && (
                  <Button onClick={onSync} loading={busy === "sync"} disabled={busy !== null}>
                    {busy !== "sync" && <RefreshCw size={15} />}
                    {busy === "sync" ? "Checking inbox…" : "Check for new alerts now"}
                  </Button>
                )}
                {gmail && (
                  <Button variant="ghost" onClick={onDisconnect} loading={busy === "disconnect"} disabled={busy !== null}>
                    {busy !== "disconnect" && <Unplug size={15} />} {busy === "disconnect" ? "Disconnecting…" : "Disconnect"}
                  </Button>
                )}
              </div>
            </div>

            {gmail && (
              <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-subtle">Connected</dt>
                  <dd className="mt-1 text-sm font-medium text-fg">
                    {new Date(gmail.connected_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                  </dd>
                </div>
                <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-subtle">Last checked</dt>
                  <dd className="mt-1 text-sm font-medium text-fg">
                    {gmail.last_polled_at
                      ? new Date(gmail.last_polled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
                      : "Not yet"}
                  </dd>
                </div>
                <div className="col-span-2 rounded-xl border border-line bg-surface-2 p-3.5 sm:col-span-1">
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-subtle">Permissions</dt>
                  <dd className="mt-1 flex gap-1.5">
                    {gmail.scopes.some((sc) => sc.endsWith("gmail.readonly")) && <Badge tone="info">Read alerts</Badge>}
                    {gmail.scopes.some((sc) => sc.endsWith("gmail.send")) && <Badge tone="accent">Send on approval</Badge>}
                  </dd>
                </div>
                {gmail.last_error && (
                  <div className="col-span-2 sm:col-span-3">
                    <Alert tone="bad">{gmail.last_error}</Alert>
                  </div>
                )}
              </dl>
            )}

            {syncResult && (
              <div className="animate-scale-in mt-5 flex flex-col gap-3 rounded-2xl border border-accent/25 bg-accent-soft p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <Inbox size={20} className="shrink-0 text-accent-fg" />
                  <div className="text-sm text-fg">
                    Checked {syncResult.messages_seen} alert email{syncResult.messages_seen === 1 ? "" : "s"} —{" "}
                    <strong>
                      {syncResult.opportunities_ingested} new opportunit{syncResult.opportunities_ingested === 1 ? "y" : "ies"}
                    </strong>
                    {syncResult.skipped_already_processed > 0 && `, ${syncResult.skipped_already_processed} already seen`}.
                    {syncResult.failures.length > 0 && (
                      <span className="text-warn"> {syncResult.failures.length} couldn&apos;t be processed.</span>
                    )}
                  </div>
                </div>
                {syncResult.opportunities_ingested > 0 && (
                  <Link href="/applications" className={buttonClasses("primary", "sm", "shrink-0")}>
                    Review them <ArrowRight size={13} />
                  </Link>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      <section>
        <SectionLabel>Your inbox, your rules</SectionLabel>
        <div className="stagger grid gap-3 sm:grid-cols-3">
          {[
            { icon: ShieldCheck, title: "Alerts only", text: "Only mail from LinkedIn & Naukri job-alert senders is ever read — never the rest of your inbox." },
            { icon: Send, title: "Never sends alone", text: "An application is only sent after you review it and explicitly approve." },
            { icon: Lock, title: "Encrypted & revocable", text: "Access tokens are encrypted at rest. Disconnecting revokes them with Google." },
          ].map(({ icon: Icon, title, text }) => (
            <Card key={title} className="p-5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ok-soft text-ok">
                <Icon size={17} />
              </span>
              <div className="mt-3 text-sm font-semibold text-fg">{title}</div>
              <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
            </Card>
          ))}
        </div>
      </section>

      {connected && (
        <p className="flex items-center gap-2 text-xs text-subtle">
          <CheckCircle2 size={14} className="text-ok" /> New alerts are checked automatically every 15–30 minutes.
        </p>
      )}
    </div>
  );
}
