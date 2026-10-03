"use client";

import { useEffect, useState } from "react";
import { Activity, Briefcase, Gauge, Users } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { CountUp } from "@/components/Motion";
import { Alert, Badge, Card, PageHeader, PageSkeleton, SectionLabel, StatCard } from "@/components/ui";

type Stats = {
  users: Record<string, number>;
  funnel: { applications: number; tailored: number; ever_applied: number; by_current_stage: Record<string, number>; avg_ats_score: number | null };
  ai_last_24h: Record<string, Record<string, number>>;
  recent_errors: { agent: string; at: string; error: string }[];
  usage_today: Record<string, number>;
  jobs: { listings: number; by_source: Record<string, number>; last_refresh: Record<string, string> };
};

const USER_LABELS: Record<string, string> = {
  total: "Users",
  new_7d: "New this week",
  active_7d: "Active this week",
  with_resume_profile: "Set target roles",
  autopilot_on: "Autopilot on",
  gmail_connected: "Gmail connected",
  gmail_errors: "Gmail needs reconnect",
};

// Founder view: growth, funnel, AI health and job-source health. Only reachable for
// ADMIN_EMAILS (the API 404s for anyone else).
export default function AdminPage() {
  const { user, loading } = useRequireAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .adminStats()
      .then((s) => setStats(s as unknown as Stats))
      .catch((err) => setError(err instanceof ApiError && err.status === 404 ? "This page is for Pathlight admins." : "Couldn't load stats."));
  }, [user]);

  if (loading || !user) return null;
  if (error) return <Alert tone="warn">{error}</Alert>;
  if (!stats) return <PageSkeleton />;

  const funnelSteps = [
    { label: "Jobs tracked", value: stats.funnel.applications },
    { label: "Resumes tailored", value: stats.funnel.tailored },
    { label: "Applied", value: stats.funnel.ever_applied },
  ];
  const maxFunnel = Math.max(1, ...funnelSteps.map((s) => s.value));

  return (
    <div className="space-y-8">
      <PageHeader title="Admin" subtitle="How Pathlight is doing — growth, the application funnel, AI health and job sources." />

      <section>
        <SectionLabel>Users</SectionLabel>
        <div className="stagger grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Object.entries(USER_LABELS).map(([key, label]) => (
            <StatCard
              key={key}
              icon={Users}
              label={label}
              value={<CountUp value={stats.users[key] ?? 0} />}
              tone={key === "gmail_errors" && stats.users[key] ? "warn" : "neutral"}
            />
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <SectionLabel>Funnel</SectionLabel>
          <Card className="space-y-4 p-5">
            {funnelSteps.map((step) => (
              <div key={step.label}>
                <div className="mb-1.5 flex justify-between text-[13px]">
                  <span className="text-muted">{step.label}</span>
                  <span className="font-semibold tabular-nums text-fg">{step.value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-hover">
                  <div className="h-full rounded-full bg-accent transition-[width] duration-1000" style={{ width: `${(step.value / maxFunnel) * 100}%` }} />
                </div>
              </div>
            ))}
            <div className="flex items-center gap-2 border-t border-line pt-3 text-[13px] text-muted">
              <Gauge size={14} /> Average ATS score:{" "}
              <span className="font-semibold text-fg">{stats.funnel.avg_ats_score ?? "—"}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(stats.funnel.by_current_stage).map(([stage, n]) => (
                <Badge key={stage}>
                  {stage.replaceAll("_", " ").toLowerCase()} · {n}
                </Badge>
              ))}
            </div>
          </Card>
        </section>

        <section>
          <SectionLabel>AI in the last 24 hours</SectionLabel>
          <Card className="divide-y divide-line">
            {Object.keys(stats.ai_last_24h).length === 0 && <p className="p-4 text-[13px] text-muted">No AI runs yet today.</p>}
            {Object.entries(stats.ai_last_24h).map(([agent, counts]) => (
              <div key={agent} className="flex items-center justify-between px-4 py-3 text-[13px]">
                <span className="flex items-center gap-2 font-medium text-fg">
                  <Activity size={13} className="text-subtle" /> {agent.replaceAll("_", " ")}
                </span>
                <span className="flex gap-1.5">
                  <Badge tone="ok">{counts.success ?? 0} ok</Badge>
                  {counts.error ? <Badge tone="bad">{counts.error} failed</Badge> : null}
                </span>
              </div>
            ))}
            <div className="px-4 py-3 text-xs text-subtle">
              Usage today:{" "}
              {Object.entries(stats.usage_today).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}
            </div>
          </Card>
        </section>
      </div>

      {stats.recent_errors.length > 0 && (
        <section>
          <SectionLabel>Recent AI errors</SectionLabel>
          <Card className="divide-y divide-line">
            {stats.recent_errors.map((e, i) => (
              <div key={i} className="px-4 py-3 text-[12.5px]">
                <div className="flex justify-between text-subtle">
                  <span className="font-medium text-fg">{e.agent}</span>
                  <span>{new Date(e.at).toLocaleString()}</span>
                </div>
                <p className="mt-1 break-words font-mono text-[11.5px] text-muted">{e.error}</p>
              </div>
            ))}
          </Card>
        </section>
      )}

      <section>
        <SectionLabel>Job sources · {stats.jobs.listings} listings</SectionLabel>
        <Card className="p-4">
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(stats.jobs.by_source).map(([source, n]) => (
              <Badge key={source} icon={Briefcase}>
                {source} · {n}
              </Badge>
            ))}
          </div>
          {Object.keys(stats.jobs.last_refresh).length > 0 && (
            <div className="mt-4 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(stats.jobs.last_refresh).map(([name, status]) => (
                <div key={name} className="flex justify-between gap-2 border-b border-line py-1">
                  <span className="truncate text-muted">{name}</span>
                  <span className={status.startsWith("ok") ? "text-ok" : status.startsWith("off") ? "text-subtle" : "text-bad"}>{status}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
