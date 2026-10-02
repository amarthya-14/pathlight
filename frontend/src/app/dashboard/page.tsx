"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  CalendarClock,
  Check,
  Compass,
  FileText,
  Layers,
  Mail,
  Plus,
  Send,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { ApplicationOut, DashboardHomeOut, IntegrationOut } from "@/lib/types";
import { currentStage } from "@/lib/stages";
import { ApplicationRow } from "@/components/ApplicationRow";
import { Alert, buttonClasses, Card, EmptyState, PageHeader, PageSkeleton, SectionLabel, StatCard } from "@/components/ui";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Burning the midnight oil";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function SetupChecklist({ hasProfile, hasResume, gmailConnected }: { hasProfile: boolean; hasResume: boolean; gmailConnected: boolean }) {
  const steps = [
    { done: hasProfile, icon: UserRound, title: "Add your CGPA & branch", text: "Unlocks eligibility checks", href: "/profile" },
    { done: hasResume, icon: FileText, title: "Upload your resume", text: "Powers skill gaps & tailoring", href: "/profile" },
    { done: gmailConnected, icon: Mail, title: "Connect Gmail", text: "Job alerts arrive automatically", href: "/integrations" },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null;
  const pct = Math.round((doneCount / steps.length) * 100);

  return (
    <Card glow className="relative overflow-hidden p-5 sm:p-6">
      <div className="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-accent/20 blur-3xl" />
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-fg">
            <Sparkles size={16} className="text-accent-fg" /> Finish setting up Pathlight
          </div>
          <p className="mt-1 text-sm text-muted">{doneCount} of 3 done — each step makes the autopilot smarter.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-2 w-36 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-brand-gradient transition-all duration-700" style={{ width: `${pct}%` }} />
          </div>
          <span className="text-sm font-semibold tabular-nums text-fg">{pct}%</span>
        </div>
      </div>
      <div className="relative mt-5 grid gap-3 sm:grid-cols-3">
        {steps.map(({ done, icon: Icon, title, text, href }) => (
          <Link
            key={title}
            href={href}
            className={`flex items-center gap-3 rounded-xl border p-3.5 transition-all ${
              done ? "border-ok/20 bg-ok-soft" : "border-line bg-surface-2 hover:border-line-strong hover:bg-surface-hover"
            }`}
          >
            <span
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                done ? "bg-ok text-white" : "bg-surface-solid text-accent-fg"
              }`}
            >
              {done ? <Check size={17} strokeWidth={2.8} /> : <Icon size={17} />}
            </span>
            <div className="min-w-0">
              <div className={`text-sm font-semibold ${done ? "text-ok" : "text-fg"}`}>{title}</div>
              <div className="truncate text-xs text-muted">{done ? "Done" : text}</div>
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [data, setData] = useState<DashboardHomeOut | null>(null);
  const [applications, setApplications] = useState<ApplicationOut[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .getDashboardHome()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"));
    api.listApplications().then(setApplications).catch(() => {});
    api.listIntegrations().then(setIntegrations).catch(() => {});
  }, [user]);

  if (authLoading || !user) return null;
  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!data) return <PageSkeleton />;

  const name = user.email.split("@")[0];
  const gmailConnected = integrations.some((i) => i.provider === "gmail" && i.status === "connected");
  const needsAttention = applications.filter((a) => {
    const s = currentStage(a);
    return s === "READY_TO_APPLY" || s === "MANUAL_APPLY_REQUIRED";
  });
  const appliedCount = applications.filter((a) => a.status_history.some((e) => e.stage === "APPLIED")).length;
  const nothingYet = data.recent_applications.length === 0;
  const maxGap = Math.max(1, data.most_common_missing_skills.length);

  return (
    <div className="space-y-10">
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
          title={`${greeting()}, ${name}`}
          subtitle={
            needsAttention.length > 0
              ? `${needsAttention.length} application${needsAttention.length === 1 ? " is" : "s are"} waiting for your review.`
              : "Here's where your placement season stands."
          }
          actions={
            <Link href="/opportunities" className={buttonClasses("primary", "md")}>
              <Plus size={16} /> Add opportunity
            </Link>
          }
        />
      </div>

      <div className="animate-fade-in" style={{ animationDelay: "0.05s" }}>
        <SetupChecklist hasProfile={data.has_profile} hasResume={data.has_resume} gmailConnected={gmailConnected} />
      </div>

      {nothingYet ? (
        <EmptyState
          icon={Compass}
          title="Your pipeline is empty — for now"
          description="Paste a job description or placement email, or connect Gmail and let job alerts flow in. Pathlight runs eligibility, skill-gap and tailoring automatically."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link href="/opportunities" className={buttonClasses("primary", "md")}>
                <Plus size={16} /> Add your first opportunity
              </Link>
              <Link href="/integrations" className={buttonClasses("secondary", "md")}>
                <Mail size={16} /> Connect Gmail
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="stagger grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard icon={Layers} value={applications.length || data.recent_applications.length} label="Opportunities tracked" />
            <StatCard icon={Sparkles} value={needsAttention.length} label="Waiting for your review" tone="accent" />
            <StatCard icon={Send} value={appliedCount} label="Applied" tone="ok" />
            <StatCard icon={CalendarClock} value={data.urgent_deadlines.length} label="Deadlines in 14 days" tone={data.urgent_deadlines.length > 0 ? "warn" : "neutral"} />
          </div>

          {needsAttention.length > 0 && (
            <section className="animate-fade-in">
              <SectionLabel
                action={
                  <Link href="/applications" className="inline-flex items-center gap-1 text-xs font-semibold text-accent-fg hover:underline">
                    All applications <ArrowRight size={13} />
                  </Link>
                }
              >
                Needs your attention
              </SectionLabel>
              <div className="stagger space-y-2.5">
                {needsAttention.slice(0, 5).map((app) => (
                  <ApplicationRow key={app.id} app={app} />
                ))}
              </div>
            </section>
          )}

          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section>
              <SectionLabel>Closing soon</SectionLabel>
              {data.urgent_deadlines.length === 0 ? (
                <Card className="flex items-center gap-3 p-5 text-sm text-muted">
                  <BadgeCheck size={18} className="text-ok" /> Nothing due in the next 14 days.
                </Card>
              ) : (
                <div className="stagger space-y-2.5">
                  {data.urgent_deadlines.map((app) => (
                    <ApplicationRow key={app.id} app={app} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <SectionLabel>Skills to work on</SectionLabel>
              <Card className="p-5">
                {data.most_common_missing_skills.length === 0 ? (
                  <p className="text-sm text-muted">No recurring gaps yet — nice.</p>
                ) : (
                  <ul className="space-y-3.5">
                    {data.most_common_missing_skills.map((skill, i) => (
                      <li key={skill}>
                        <div className="mb-1.5 flex items-center justify-between text-sm">
                          <span className="font-medium text-fg">{skill}</span>
                          <span className="text-xs text-subtle">#{i + 1}</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-rose-400 to-violet-500"
                            style={{ width: `${100 - (i / maxGap) * 55}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4 text-center">
                  <div>
                    <div className="text-xl font-semibold text-bad">{data.total_missing_skills}</div>
                    <div className="text-xs text-subtle">missing, across roles</div>
                  </div>
                  <div>
                    <div className="text-xl font-semibold text-warn">{data.total_weak_skills}</div>
                    <div className="text-xs text-subtle">weak, across roles</div>
                  </div>
                </div>
              </Card>
            </section>
          </div>

          <section>
            <SectionLabel
              action={
                <Link href="/opportunities" className="inline-flex items-center gap-1 text-xs font-semibold text-accent-fg hover:underline">
                  View all <ArrowRight size={13} />
                </Link>
              }
            >
              Recently discovered
            </SectionLabel>
            <div className="stagger space-y-2.5">
              {data.recent_applications.map((app) => (
                <ApplicationRow key={app.id} app={app} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
