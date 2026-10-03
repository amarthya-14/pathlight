"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check, ClipboardCopy, Forward, Inbox, KeyRound, ShieldCheck, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AlertAddress } from "@/lib/types";
import { Badge, Button, buttonClasses, Card, cx, Skeleton } from "./ui";

// What goes in Gmail's filter "From" box: LinkedIn and Naukri alert senders only.
export const ALERT_FROM = "jobalerts-noreply@linkedin.com OR jobs-noreply@linkedin.com OR naukri.com";

function ago(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function Copy({ text, label = "Copy", big = false }: { text: string; label?: string; big?: boolean }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          // clipboard blocked — the text is visible to copy by hand
        }
      }}
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-md border font-medium transition-colors duration-200",
        big ? "h-9 px-3 text-[13px]" : "h-7 px-2 text-xs",
        done ? "border-ok/30 bg-ok-soft text-ok" : "border-line-strong bg-surface text-muted hover:text-fg"
      )}
    >
      {done ? <Check size={13} strokeWidth={2.6} /> : <ClipboardCopy size={13} />}
      {done ? "Copied" : label}
    </button>
  );
}

function Step({ n, title, children, done }: { n: number; title: string; children: React.ReactNode; done?: boolean }) {
  return (
    <li className="flex gap-3.5">
      <span
        className={cx(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
          done ? "bg-ok text-white" : "bg-ink text-ink-fg"
        )}
      >
        {done ? <Check size={12} strokeWidth={3} /> : n}
      </span>
      <div className="min-w-0 flex-1 pb-1">
        <div className="text-[13.5px] font-medium text-fg">{title}</div>
        <div className="mt-1 space-y-2 text-[13px] leading-relaxed text-muted [&_strong]:font-medium [&_strong]:text-fg">{children}</div>
      </div>
    </li>
  );
}

// Forward LinkedIn/Naukri alerts to a private Pathlight address. Works for everyone:
// Pathlight never asks for access to the inbox, so Google's Gmail review doesn't apply.
export function AlertForwardingCard() {
  const [data, setData] = useState<AlertAddress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rotating, setRotating] = useState<"ask" | "busy" | null>(null);

  const load = useCallback(() => {
    api
      .alertAddress()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load your forwarding address"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const hasAlert = data?.activity.some((a) => a.kind === "job_alert") ?? false;
  const confirmation = data?.activity.find((a) => a.kind === "gmail_confirmation");
  const confirmedOrReceiving = hasAlert;

  // While setting up, check every 10s so Gmail's confirmation code shows up on its own.
  useEffect(() => {
    if (!data?.enabled || hasAlert) return;
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, [data?.enabled, hasAlert, load]);

  if (error) return null;
  if (!data) return <Skeleton className="h-72" />;

  if (!data.enabled) {
    return (
      <Card className="flex items-start gap-4 p-5 sm:p-6">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-2">
          <Forward size={19} className="text-subtle" />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-[15px] font-semibold text-fg">Forward your job alerts</h2>
            <Badge>Coming soon</Badge>
          </div>
          <p className="mt-1 max-w-lg text-[13px] leading-relaxed text-muted">
            Soon you&apos;ll get a private Pathlight address to forward LinkedIn and Naukri alerts to. Until then, find roles
            in Jobs for you or paste any posting into Add a job.
          </p>
        </div>
      </Card>
    );
  }

  const status = hasAlert
    ? { tone: "ok" as const, text: `Receiving · last alert ${ago(data.activity.find((a) => a.kind === "job_alert")!.received_at)}` }
    : confirmation
      ? { tone: "accent" as const, text: "Gmail sent a confirmation code" }
      : { tone: "neutral" as const, text: "Waiting for setup" };

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-2">
            <Forward size={19} className="text-fg" strokeWidth={1.8} />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-[15px] font-semibold text-fg">Forward your job alerts</h2>
              <Badge tone="ok">Recommended</Badge>
              <Badge tone={status.tone} dot>
                {status.text}
              </Badge>
            </div>
            <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-muted">
              One Gmail filter sends only your LinkedIn and Naukri alerts to your private Pathlight address. Every job in
              them is checked, matched to your resume and tailored — Pathlight never sees the rest of your inbox.
            </p>
          </div>
        </div>
      </div>

      <div className="border-t border-line bg-surface-2/50 px-5 py-4 sm:px-6">
        <div className="text-xs font-medium text-subtle">Your private Pathlight address</div>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <code className="min-w-0 break-all rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[13.5px] text-fg">{data.address}</code>
          <Copy text={data.address!} label="Copy address" big />
        </div>
      </div>

      {confirmation && !hasAlert && (
        <div className="animate-scale-in border-t border-line bg-accent-soft px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[13.5px] font-semibold text-fg">Gmail sent your confirmation code</div>
              <p className="text-[13px] text-muted">Paste it in Gmail&apos;s forwarding settings and click Verify — or open the link.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {confirmation.confirmation_code && (
                <>
                  <code className="rounded-lg bg-surface px-3 py-1.5 font-mono text-[15px] font-semibold tracking-wider text-fg">
                    {confirmation.confirmation_code}
                  </code>
                  <Copy text={confirmation.confirmation_code} />
                </>
              )}
              {confirmation.confirmation_link && (
                <a href={confirmation.confirmation_link} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "sm")}>
                  Open link <ArrowUpRight size={12} />
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="border-t border-line px-5 py-5 sm:px-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="text-[13px] font-semibold text-fg">Set it up once — about 3 minutes, on a computer</div>
          <a href="https://mail.google.com/mail/u/0/#settings/fwdandpop" target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "sm")}>
            Open Gmail settings <ArrowUpRight size={12} />
          </a>
        </div>
        <ol className="space-y-4">
          <Step n={1} title="Add your Pathlight address in Gmail" done={Boolean(confirmation) || hasAlert}>
            <p>
              In Gmail: <strong>⚙ Settings → See all settings → Forwarding and POP/IMAP → Add a forwarding address</strong>.
              Paste your address above → <strong>Next → Proceed</strong>.
            </p>
          </Step>
          <Step n={2} title="Confirm it" done={hasAlert}>
            <p>
              Gmail emails a confirmation code to Pathlight — it appears on this page within a minute. Paste it in Gmail and
              click <strong>Verify</strong>. Leave <strong>Disable forwarding</strong> selected there: the filter in the next
              step forwards only your alerts.
            </p>
          </Step>
          <Step n={3} title="Create the alert filter" done={hasAlert}>
            <p>
              In Gmail&apos;s search bar, click <strong>Show search options</strong> (the sliders icon). In <strong>From</strong>, paste:
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="break-all rounded-md bg-surface-hover px-2 py-1 font-mono text-[12px] text-fg">{ALERT_FROM}</code>
              <Copy text={ALERT_FROM} />
            </div>
            <p>
              Click <strong>Create filter</strong> → tick <strong>Forward it to</strong> → pick your Pathlight address →{" "}
              <strong>Create filter</strong>. New alerts flow in automatically from now on.
            </p>
          </Step>
        </ol>
        <p className="mt-4 flex items-start gap-1.5 text-xs leading-relaxed text-subtle">
          <ShieldCheck size={13} className="mt-[1px] shrink-0 text-ok" />
          Gmail&apos;s phone app can&apos;t add forwarding — use Gmail on a computer once. Anything that isn&apos;t a job alert is
          ignored and never stored.
        </p>
      </div>

      {data.activity.length > 0 && (
        <div className="border-t border-line">
          <div className="px-5 pt-4 text-xs font-medium text-subtle sm:px-6">Recent</div>
          <ul className="divide-y divide-line">
            {data.activity.slice(0, 5).map((a, i) => (
              <li key={i} className="flex items-center gap-3 px-5 py-3 text-[13px] sm:px-6">
                {a.kind === "job_alert" ? (
                  a.status === "failed" ? <TriangleAlert size={15} className="shrink-0 text-bad" /> : <Inbox size={15} className="shrink-0 text-muted" />
                ) : a.kind === "gmail_confirmation" ? (
                  <KeyRound size={15} className="shrink-0 text-accent" />
                ) : (
                  <Forward size={15} className="shrink-0 text-subtle" />
                )}
                <span className="min-w-0 flex-1 truncate text-fg">
                  {a.kind === "gmail_confirmation" ? "Gmail forwarding confirmation" : a.kind === "ignored" ? "Ignored — not a job alert" : a.subject}
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {a.kind === "job_alert" &&
                    (a.status === "processing"
                      ? "Reading…"
                      : a.status === "failed"
                        ? "Couldn't process"
                        : `${a.jobs_ingested} job${a.jobs_ingested === 1 ? "" : "s"} added${a.skipped_not_relevant ? ` · ${a.skipped_not_relevant} skipped` : ""}`)}
                </span>
                <span className="w-20 shrink-0 text-right text-xs text-subtle">{ago(a.received_at)}</span>
              </li>
            ))}
          </ul>
          {hasAlert && (
            <div className="flex justify-end px-5 pb-4 sm:px-6">
              <Link href="/applications" className="flex items-center gap-1 text-[13px] text-muted hover:text-fg">
                See them in Applications <ArrowRight size={13} />
              </Link>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-5 py-3 text-xs text-subtle sm:px-6">
        <span>{confirmedOrReceiving ? "Forwarding is working." : "Tip: keep this page open while you set it up."}</span>
        {rotating === "ask" ? (
          <span className="flex items-center gap-2">
            Your Gmail filter will stop working until you update it.
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                setRotating("busy");
                try {
                  setData(await api.rotateAlertAddress());
                } finally {
                  setRotating(null);
                }
              }}
            >
              Get new address
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRotating(null)}>
              Cancel
            </Button>
          </span>
        ) : (
          <button onClick={() => setRotating("ask")} className="hover:text-fg hover:underline" disabled={rotating === "busy"}>
            Getting spam here? Get a new address
          </button>
        )}
      </div>
    </Card>
  );
}
