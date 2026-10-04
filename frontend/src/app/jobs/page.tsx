"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check, Compass, CornerDownLeft, EyeOff, Globe2, Loader2, MapPin, Plus, RefreshCw, Search, Sparkles, X } from "lucide-react";
import { firstName, useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { JobFeedItem, JobFeedOut, JobFeedParams, JobType, JobWebSearchOut } from "@/lib/types";
import { useToast } from "@/components/Toast";
import { Reveal } from "@/components/Motion";
import { Alert, Badge, Button, buttonClasses, Card, CompanyAvatar, cx, EmptyState, PageHeader, Skeleton, type Tone } from "@/components/ui";

const FILTERS = [
  { key: "all", label: "Anywhere" },
  { key: "india", label: "In India" },
  { key: "remote", label: "Remote" },
] as const;

const JOB_TYPES: { key: JobType | null; label: string }[] = [
  { key: null, label: "All types" },
  { key: "internship", label: "Internship" },
  { key: "full_time", label: "Full-time" },
  { key: "part_time", label: "Part-time" },
];
const TYPE_LABEL: Record<JobType, string> = {
  internship: "Internship",
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
};
const TYPE_TONE: Record<JobType, Tone> = { internship: "accent", full_time: "neutral", part_time: "info", contract: "warn" };
// What a web search is called in a sentence: "python internships".
const TYPE_PLURAL: Record<JobType, string> = {
  internship: "internships",
  full_time: "full-time roles",
  part_time: "part-time roles",
  contract: "contract roles",
};
const WEB_SOURCES = "Himalayas, Remotive, Jobicy, The Muse and Indian job boards";
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
  job_type: "are other job types",
  dismissed: "you hid",
};
const PREFS_KEY = "pathlight_job_filters";

type Prefs = { minMatch: number; days: number; includeExperienced: boolean; jobType: JobType | null };
const DEFAULT_PREFS: Prefs = { minMatch: 60, days: 30, includeExperienced: false, jobType: null };

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
  return (
    {
      greenhouse: "Careers page",
      lever: "Careers page",
      ashby: "Careers page",
      smartrecruiters: "Careers page",
      remotive: "Remotive",
      himalayas: "Himalayas",
      arbeitnow: "Arbeitnow",
      jobicy: "Jobicy",
      themuse: "The Muse",
      adzuna: "Adzuna",
      jooble: "Jooble",
    }[source] ?? source
  );
}

function Segmented<T extends string | number | null>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { key: T; label: string; count?: number }[];
  value: T;
  onChange: (key: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex max-w-full gap-0.5 overflow-x-auto rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map((o) => {
        const active = o.key === value;
        return (
          <button
            key={String(o.key)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.key)}
            className={cx(
              "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-[12.5px] font-medium transition-[background-color,color,box-shadow] duration-200",
              active ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:text-fg"
            )}
          >
            {o.label}
            {o.count !== undefined && (
              <span className={cx("tabular-nums text-[11px]", active ? "text-muted" : "text-subtle")}>{o.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function SelectChip({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  options: { value: number; label: string }[];
}) {
  return (
    <label className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line bg-surface pl-2.5 pr-1 text-[12.5px] text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-7 cursor-pointer rounded-md bg-transparent pr-1 text-[12.5px] font-medium text-fg focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
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
  isNew,
}: {
  job: JobFeedItem;
  onTrack: () => void;
  onDismiss: () => void;
  state: "idle" | "busy" | "added" | "dismissed";
  isNew: boolean;
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
              {(isNew || job.job_type !== "full_time") && (
                <div className="mb-1.5 flex flex-wrap gap-1.5">
                  {isNew && (
                    <Badge tone="ok" dot>
                      New from the web
                    </Badge>
                  )}
                  {job.job_type !== "full_time" && <Badge tone={TYPE_TONE[job.job_type]}>{TYPE_LABEL[job.job_type]}</Badge>}
                </div>
              )}
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
                {job.job_type === "full_time" && (
                  <>
                    <span className="text-line-strong">·</span>
                    <span>Full-time</span>
                  </>
                )}
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

type WebState =
  | { phase: "idle" }
  | { phase: "searching"; q: string; jobType: JobType | null }
  | { phase: "done"; q: string; jobType: JobType | null; result: JobWebSearchOut; fitting: number }
  | { phase: "error"; message: string };

function searchPhrase(q: string, jobType: JobType | null): string {
  const what = jobType ? TYPE_PLURAL[jobType] : "roles";
  return q ? `“${q}” ${what}` : what;
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
  const [web, setWeb] = useState<WebState>({ phase: "idle" });
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

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

  const load = useCallback(async (params: JobFeedParams) => {
    setError(null);
    try {
      const next = await api.jobFeed(params);
      setFeed(next);
      return next;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load jobs");
      return null;
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
    let all = feed?.items ?? [];
    if (filter === "remote") all = all.filter((j) => j.remote);
    if (filter === "india") all = all.filter((j) => !j.remote);
    // Just found on the web: those first, so the search visibly did something.
    if (newIds.size) all = [...all.filter((j) => newIds.has(j.id)), ...all.filter((j) => !newIds.has(j.id))];
    return all;
  }, [feed, filter, newIds]);

  if (authLoading || !user) return null;

  const roles = profile?.target_roles ?? [];

  const searchWeb = async () => {
    if (web.phase === "searching") return;
    // No query: search for what the student is looking for.
    const q = query.trim() || roles[0] || "";
    const jobType = prefs.jobType;
    setWeb({ phase: "searching", q, jobType });
    try {
      const result = await api.searchJobsOnWeb(q, jobType);
      const next = await load({ q: query.trim() || undefined, ...prefs });
      const added = new Set(result.new_ids);
      const fitting = next ? next.items.filter((j) => added.has(j.id)).length : 0;
      setNewIds(added);
      setWeb({ phase: "done", q, jobType, result, fitting });
    } catch (err) {
      setWeb({ phase: "error", message: err instanceof ApiError ? err.detail : "Couldn't reach the job sites" });
    }
  };

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
        .filter(([key, n]) => n > 0 && HIDDEN_LABELS[key])
        .sort((a, b) => b[1] - a[1])
    : [];

  const updated = feed?.refreshed_at ? ago(feed.refreshed_at) : null;
  const customised =
    prefs.jobType !== DEFAULT_PREFS.jobType ||
    prefs.days !== DEFAULT_PREFS.days ||
    prefs.minMatch !== DEFAULT_PREFS.minMatch ||
    prefs.includeExperienced !== DEFAULT_PREFS.includeExperienced ||
    filter !== "all";
  const resetFilters = () => {
    setPrefs({ ...DEFAULT_PREFS });
    setFilter("all");
  };
  const typeCounts = feed?.job_types;
  const allCount = typeCounts ? Object.values(typeCounts).reduce((a, b) => a + b, 0) : undefined;
  const webLabel = searchPhrase(query.trim() || roles[0] || "", prefs.jobType);
  const searching = web.phase === "searching";

  const webCta = (
    <Button variant="secondary" onClick={searchWeb} loading={searching}>
      {!searching && <Globe2 size={13} />} Search job sites for {webLabel}
    </Button>
  );

  return (
    <div className="space-y-5">
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

      <Card className="overflow-hidden p-0">
        <form
          className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center"
          onSubmit={(e) => {
            e.preventDefault();
            searchWeb();
          }}
        >
          <div className="relative flex-1">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search a role, skill, company or city"
              aria-label="Search jobs"
              className="h-10 w-full rounded-lg border border-line-strong bg-surface pl-9 pr-9 text-sm text-fg shadow-xs placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-subtle hover:bg-surface-hover hover:text-fg"
              >
                <X size={13} />
              </button>
            )}
          </div>
          <Button type="submit" size="lg" loading={searching} title="Search job sites live and add what's found to your feed">
            {!searching && <Globe2 size={14} />} Search the web
          </Button>
        </form>
        <div className="flex flex-col gap-2.5 border-t border-line bg-surface-2/50 px-3 py-2.5 lg:flex-row lg:flex-wrap lg:items-center">
          <Segmented
            label="Job type"
            value={prefs.jobType}
            onChange={(jobType) => setPrefs({ jobType })}
            options={JOB_TYPES.map((t) => ({
              ...t,
              count: t.key === null ? allCount : typeCounts?.[t.key],
            }))}
          />
          <Segmented label="Location" value={filter} onChange={setFilter} options={[...FILTERS]} />
          <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
            <SelectChip
              label="Posted"
              value={prefs.days}
              onChange={(days) => setPrefs({ days })}
              options={WINDOWS.map((w) => ({ value: w.days, label: w.label }))}
            />
            <SelectChip
              label="Match"
              value={prefs.minMatch}
              onChange={(minMatch) => setPrefs({ minMatch })}
              options={THRESHOLDS.map((t) => ({ value: t, label: `${t}%+` }))}
            />
            <label className="inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-2.5 text-[12.5px] text-muted">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-[var(--ink)]"
                checked={prefs.includeExperienced}
                onChange={(e) => setPrefs({ includeExperienced: e.target.checked })}
              />
              Roles needing experience
            </label>
            {customised && (
              <button onClick={resetFilters} className="h-8 px-1.5 text-[12.5px] font-medium text-muted underline-offset-4 hover:text-fg hover:underline">
                Reset
              </button>
            )}
          </div>
        </div>
      </Card>

      <p className="-mt-2 flex items-center gap-1.5 px-1 text-[12px] text-subtle">
        Typing filters your feed instantly. Press <CornerDownLeft size={11} className="inline" /> Enter to also search job sites live for more.
      </p>

      {searching && (
        <Card className="sweep flex items-center gap-3 p-4 text-[13px] text-muted">
          <Loader2 size={15} className="animate-spin text-accent" />
          <span>
            Searching {WEB_SOURCES} for <span className="font-medium text-fg">{searchPhrase(web.q, web.jobType)}</span>…
          </span>
        </Card>
      )}
      {web.phase === "done" && (
        <Alert
          tone={web.result.new > 0 ? "ok" : "info"}
          title={
            web.result.cached
              ? `Already searched the web for ${searchPhrase(web.q, web.jobType)} recently`
              : web.result.new > 0
                ? `Added ${web.result.new} new ${web.result.new === 1 ? "role" : "roles"} from the web`
                : `No new ${searchPhrase(web.q, web.jobType)} on the web right now`
          }
          action={
            <button onClick={() => setWeb({ phase: "idle" })} aria-label="Dismiss" className="rounded p-0.5 opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          }
        >
          {web.result.cached
            ? "Those results are already in your feed below."
            : web.result.new > 0
              ? web.fitting > 0
                ? `${web.fitting} fit your filters and are at the top, marked New. The rest didn't match your field, level or filters.`
                : "None passed your current filters — try a lower match threshold, a longer time window, or another job type."
              : web.result.found > 0
                ? `Found ${web.result.found}, all already in your feed.`
                : "Try a broader search — a role or a skill rather than a company."}
        </Alert>
      )}
      {web.phase === "error" && (
        <Alert
          tone="bad"
          action={
            <button onClick={() => setWeb({ phase: "idle" })} aria-label="Dismiss" className="rounded p-0.5 opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          }
        >
          {web.message}
        </Alert>
      )}

      {error && <Alert tone="bad">{error}</Alert>}

      {hiddenSummary.length > 0 && (
        <p className="px-1 text-[12.5px] leading-relaxed text-subtle">
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
          title={
            query
              ? `Nothing in your feed for “${query}”${prefs.jobType ? ` · ${TYPE_LABEL[prefs.jobType]}` : ""}`
              : prefs.jobType
                ? `No ${TYPE_PLURAL[prefs.jobType]} fit these filters yet`
                : "No roles fit these filters right now"
          }
          description={
            query
              ? "Search the job sites live — new matches are added to your feed."
              : prefs.days < 90
                ? "Search the job sites live, or try “Past 3 months” or a lower match threshold."
                : "Search the job sites live, or try a lower match threshold."
          }
          action={webCta}
        />
      ) : (
        <div className="space-y-3">
          {items.map((job, i) => (
            <Reveal key={job.id} delay={Math.min(i, 6) * 60}>
              <JobCard
                job={job}
                isNew={newIds.has(job.id)}
                state={states[job.id] ?? "idle"}
                onTrack={() => track(job)}
                onDismiss={() => dismiss(job)}
              />
            </Reveal>
          ))}
          <Card className="flex flex-col items-center gap-3 border-dashed p-5 text-center sm:flex-row sm:text-left">
            <div className="flex-1">
              <div className="text-[13.5px] font-medium text-fg">Want more?</div>
              <div className="mt-0.5 text-[12.5px] text-muted">
                Search {WEB_SOURCES} live — new roles that fit are added here.
              </div>
            </div>
            {webCta}
          </Card>
          <p className="pt-1 text-center text-xs text-subtle">
            Listings come straight from each company&apos;s public job board and from job aggregators.
          </p>
        </div>
      )}
    </div>
  );
}
