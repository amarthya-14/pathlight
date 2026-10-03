"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check, Compass, EyeOff, Globe2, Loader2, MapPin, Plus, RefreshCw, Search, SlidersHorizontal, Sparkles } from "lucide-react";
import { firstName, useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { JobFeedItem, JobFeedOut, JobFeedParams } from "@/lib/types";
import { useToast } from "@/components/Toast";
import { Reveal } from "@/components/Motion";
import { Alert, Badge, Button, buttonClasses, Card, CompanyAvatar, cx, EmptyState, PageHeader, Skeleton } from "@/components/ui";

const FILTERS = [
  { key: "all", label: "All matches" },
  { key: "india", label: "In India" },
  { key: "remote", label: "Remote" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

const WINDOWS = [
  { days: 7, label: "Past week" },
  { days: 30, label: "Past month" },
  { days: 90, label: "Past 3 months" },
];
const THRESHOLDS = [50, 60, 70, 80];
const HIDDEN_LABELS: Record<keyof JobFeedOut["hidden"], string> = {
  experience: "need experience you don't have yet",
  field: "are outside your field",
  old: "are older",
  batch: "are for other batches",
  low_match: "match less",
  dismissed: "you hid",
};
const PREFS_KEY = "pathlight_job_filters";

type Prefs = { minMatch: number; days: number; includeExperienced: boolean };
const DEFAULT_PREFS: Prefs = { minMatch: 60, days: 30, includeExperienced: false };

function loadPrefs(): Prefs {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(window.localStorage.getItem(PREFS_KEY) ?? "{}") };
  } catch {
    return DEFAULT_PREFS;
  }
}

function ago(iso: string | null): string | null {
  if (!iso) return null;
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function sourceLabel(source: string): string {
  return { greenhouse: "Careers page", lever: "Careers page", remotive: "Remotive", himalayas: "Himalayas", arbeitnow: "Arbeitnow" }[source] ?? source;
}

function MatchMeter({ value }: { value: number }) {
  const tone = value >= 70 ? "bg-ok" : value >= 45 ? "bg-accent" : "bg-subtle";
  return (
    <div className="flex items-center gap-2" title={`${value}% match with your profile`}>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-hover">
        <div className={cx("h-full rounded-full transition-[width] duration-1000", tone)} style={{ width: `${value}%` }} />
      </div>
      <span className="w-9 text-right text-xs font-semibold tabular-nums text-fg">{value}%</span>
    </div>
  );
}

function JobCard({
  job,
  onTrack,
  onDismiss,
  state,
}: {
  job: JobFeedItem;
  onTrack: () => void;
  onDismiss: () => void;
  state: "idle" | "busy" | "added" | "dismissed";
}) {
  const tracked = job.tracked_application_id;
  return (
    <Card
      className={cx(
        "lift p-4 transition-[opacity,transform,filter] duration-500 sm:p-5",
        state === "dismissed" && "pointer-events-none -translate-x-3 opacity-0 blur-[2px]"
      )}
    >
      <div className="flex items-start gap-3.5">
        <CompanyAvatar name={job.company} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
            <div className="min-w-0">
              <a href={job.url} target="_blank" rel="noopener noreferrer" className="group inline-flex items-start gap-1 text-[15px] font-semibold leading-snug text-fg">
                <span className="group-hover:underline group-hover:decoration-line-strong group-hover:underline-offset-4">{job.title}</span>
                <ArrowUpRight size={14} className="mt-1 shrink-0 text-subtle transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </a>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px] text-muted">
                <span className="font-medium text-fg/80">{job.company}</span>
                <span className="text-line-strong">·</span>
                <span className="inline-flex items-center gap-1">
                  {job.remote ? <Globe2 size={12} /> : <MapPin size={12} />}
                  {job.location || (job.remote ? "Remote" : "—")}
                </span>
                {ago(job.posted_at) && (
                  <>
                    <span className="text-line-strong">·</span>
                    <span>{ago(job.posted_at)}</span>
                  </>
                )}
              </div>
            </div>
            <MatchMeter value={job.match} />
          </div>

          {(job.matched_skills.length > 0 || job.missing_skills.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.matched_skills.slice(0, 6).map((s) => (
                <Badge key={s} tone="ok">
                  <Check size={11} strokeWidth={2.8} /> {s}
                </Badge>
              ))}
              {job.missing_skills.slice(0, 3).map((s) => (
                <Badge key={s} className="text-subtle">
                  {s}
                </Badge>
              ))}
            </div>
          )}

          {job.reasons.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted">
              {job.reasons.map((r, i) => (
                <span key={r} className="inline-flex items-center gap-2.5">
                  {i > 0 && <span className="text-line-strong">·</span>}
                  <span className={r === "Entry-level" ? "font-medium text-ok" : ""}>{r}</span>
                </span>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-subtle">via {sourceLabel(job.source)}</span>
            <div className="flex gap-2">
              {!tracked && state === "idle" && (
                <Button size="sm" variant="ghost" onClick={onDismiss} title="Hide this job">
                  <EyeOff size={12} /> Not for me
                </Button>
              )}
              {tracked ? (
                <Link href={`/applications/${tracked}`} className={buttonClasses("secondary", "sm")}>
                  <Check size={12} className="text-ok" strokeWidth={2.6} /> Tracked — open
                </Link>
              ) : state === "added" ? (
                <span className="inline-flex h-7 items-center gap-1.5 rounded-md bg-ok-soft px-2.5 text-xs font-medium text-ok">
                  <Loader2 size={12} className="animate-spin" /> Analysing — appears in Applications shortly
                </span>
              ) : (
                <Button size="sm" onClick={onTrack} loading={state === "busy"}>
                  {state !== "busy" && <Plus size={13} />} Track & tailor resume
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function JobsPage() {
  const { user, profile, loading: authLoading } = useRequireAuth();
  const toast = useToast();
  const [feed, setFeed] = useState<JobFeedOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [prefs, setPrefsState] = useState<Prefs>(DEFAULT_PREFS);
  const [prefsReady, setPrefsReady] = useState(false);
  const [states, setStates] = useState<Record<string, "busy" | "added" | "dismissed">>({});

  useEffect(() => {
    setPrefsState(loadPrefs());
    setPrefsReady(true);
  }, []);
  const setPrefs = (patch: Partial<Prefs>) =>
    setPrefsState((p) => {
      const next = { ...p, ...patch };
      try {
        window.localStorage.setItem(PREFS_KEY, JSON.stringify(next));
      } catch {
        // per-device convenience only
      }
      return next;
    });
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (params: JobFeedParams) => {
    setError(null);
    try {
      setFeed(await api.jobFeed(params));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load jobs");
    }
  }, []);

  // One request on arrival; typing searches every cached listing (not just the top
  // ranked), debounced.
  const firstLoad = useRef(true);
  useEffect(() => {
    if (!user || !prefsReady) return;
    const delay = firstLoad.current ? 0 : 300;
    firstLoad.current = false;
    const t = setTimeout(() => load({ q: query.trim() || undefined, ...prefs }), delay);
    return () => clearTimeout(t);
  }, [query, prefs, prefsReady, user, load]);

  const items = useMemo(() => {
    const all = feed?.items ?? [];
    if (filter === "remote") return all.filter((j) => j.remote);
    if (filter === "india") return all.filter((j) => !j.remote);
    return all;
  }, [feed, filter]);

  if (authLoading || !user) return null;

  const track = async (job: JobFeedItem) => {
    setStates((s) => ({ ...s, [job.id]: "busy" }));
    try {
      await api.trackJob(job.id);
      setStates((s) => ({ ...s, [job.id]: "added" }));
      toast(`Tracking ${job.title}`, {
        description: "Checking eligibility, skill gaps and tailoring your resume — usually 1–3 minutes.",
      });
    } catch (err) {
      setStates((s) => {
        const next = { ...s };
        delete next[job.id];
        return next;
      });
      toast(err instanceof ApiError ? err.detail : "Couldn't track that job", { tone: "bad" });
    }
  };

  const refresh = async () => {
    setRefreshing(true);
    await load({ q: query.trim() || undefined, ...prefs });
    setRefreshing(false);
  };

  const dismiss = async (job: JobFeedItem) => {
    setStates((s) => ({ ...s, [job.id]: "dismissed" }));
    try {
      await api.dismissJob(job.id);
      // Let the card fade out before it leaves the list.
      setTimeout(() => setFeed((f) => (f ? { ...f, items: f.items.filter((j) => j.id !== job.id) } : f)), 450);
    } catch {
      setStates((s) => {
        const next = { ...s };
        delete next[job.id];
        return next;
      });
    }
  };

  const hiddenSummary = feed
    ? (Object.entries(feed.hidden) as [keyof JobFeedOut["hidden"], number][])
        .filter(([, n]) => n > 0)
        .sort((a, b) => b[1] - a[1])
    : [];

  const roles = profile?.target_roles ?? [];
  const updated = feed?.refreshed_at ? ago(feed.refreshed_at) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          feed ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className={cx("absolute inline-flex h-full w-full rounded-full bg-ok", feed.refreshing && "animate-ping opacity-60")} />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ok" />
              </span>
              {feed.refreshing
                ? "Refreshing from job boards…"
                : `${feed.matching} of ${feed.total_listings} open roles fit you · updated ${updated ?? "just now"}`}
            </span>
          ) : (
            "Searching job boards…"
          )
        }
        title={`Jobs for you, ${firstName(user)}`}
        subtitle={
          roles.length
            ? `Only roles in your field (${roles.slice(0, 3).join(", ")}), at your level, matched against your resume.`
            : "Only roles in your field and at your level, matched against the skills on your resume."
        }
        actions={
          <Button variant="secondary" onClick={refresh} loading={refreshing}>
            {!refreshing && <RefreshCw size={13} />} Refresh
          </Button>
        }
      />

      {feed && !feed.personalized && (
        <Alert
          tone="info"
          title="Make these matches yours"
          action={
            <Link href="/welcome" className={buttonClasses("secondary", "sm")}>
              Add roles & resume <ArrowRight size={12} />
            </Link>
          }
        >
          Add the roles you want and upload your resume — ranking uses both.
        </Alert>
      )}

      <Card className="flex flex-col gap-3 p-3 sm:flex-row sm:flex-wrap sm:items-center">
        <span className="flex items-center gap-1.5 px-1 text-[13px] font-medium text-fg">
          <SlidersHorizontal size={14} className="text-subtle" /> Show
        </span>
        <div className="flex gap-1 rounded-lg border border-line bg-surface-2 p-0.5">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              onClick={() => setPrefs({ days: w.days })}
              aria-pressed={prefs.days === w.days}
              className={cx(
                "h-7 rounded-md px-2.5 text-[12.5px] font-medium transition-[background-color,color,box-shadow] duration-200",
                prefs.days === w.days ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:text-fg"
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-[13px] text-muted">
          Match at least
          <select
            value={prefs.minMatch}
            onChange={(e) => setPrefs({ minMatch: Number(e.target.value) })}
            className="h-8 rounded-lg border border-line-strong bg-surface px-2 text-[13px] font-medium text-fg"
          >
            {THRESHOLDS.map((t) => (
              <option key={t} value={t}>
                {t}%
              </option>
            ))}
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] text-muted sm:ml-auto">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 accent-[var(--ink)]"
            checked={prefs.includeExperienced}
            onChange={(e) => setPrefs({ includeExperienced: e.target.checked })}
          />
          Include roles that need experience
        </label>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1 rounded-lg border border-line bg-surface-2 p-0.5" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={cx(
                "h-7 rounded-md px-3 text-[13px] font-medium transition-[background-color,color,box-shadow] duration-200",
                filter === f.key ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:text-fg"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search role, company or city"
            className="h-9 w-full rounded-lg border border-line-strong bg-surface pl-8 pr-3 text-sm text-fg shadow-xs placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
          />
        </div>
      </div>

      {error && <Alert tone="bad">{error}</Alert>}

      {hiddenSummary.length > 0 && (
        <p className="text-[12.5px] leading-relaxed text-subtle">
          Hidden so you don&apos;t waste time:{" "}
          {hiddenSummary.map(([key, n], i) => (
            <span key={key}>
              {i > 0 && " · "}
              <span className="font-medium text-muted">{n}</span> {HIDDEN_LABELS[key]}
            </span>
          ))}
          .
        </p>
      )}

      {!feed && !error ? (
        <div className="space-y-3">
          <Card className="sweep flex items-center gap-3 p-4 text-[13px] text-muted">
            <Sparkles size={15} className="text-accent" /> Checking company career pages and job boards for roles that fit you — the first search takes a few seconds.
          </Card>
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Compass}
          title={query ? `Nothing matching “${query}”` : "No roles fit these filters right now"}
          description={
            query
              ? "Try a broader search — a skill, a city, or a company."
              : prefs.days < 90
                ? "Try “Past 3 months” or a lower match threshold. Boards refresh twice a day."
                : "Try a lower match threshold, or check back tomorrow — boards refresh twice a day."
          }
        />
      ) : (
        <div className="space-y-3">
          {items.map((job, i) => (
            <Reveal key={job.id} delay={Math.min(i, 6) * 60}>
              <JobCard job={job} state={states[job.id] ?? "idle"} onTrack={() => track(job)} onDismiss={() => dismiss(job)} />
            </Reveal>
          ))}
          <p className="pt-2 text-center text-xs text-subtle">
            Listings come straight from each company&apos;s public job board and from job aggregators.
          </p>
        </div>
      )}
    </div>
  );
}
