"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, CalendarClock, Check, Compass, FileText, Layers, Mail, Plus, Send, Sparkles, Target } from "lucide-react";
import { firstName, useRequireAuth } from "@/lib/auth-context";
import { CountUp, Reveal } from "@/components/Motion";
import { api } from "@/lib/api";
import type { ApplicationOut, DashboardHomeOut, IntegrationOut, JobFeedItem } from "@/lib/types";
import { currentStage, daysUntil, deadlineLabel, deadlineTone } from "@/lib/stages";
import { ApplicationRow, RowList } from "@/components/ApplicationRow";
import { Alert, Badge, buttonClasses, Card, CompanyAvatar, EmptyState, PageHeader, PageSkeleton, Progress, SectionLabel, StatCard } from "@/components/ui";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function SetupChecklist({ hasGoals, hasResume, gmailConnected }: { hasGoals: boolean; hasResume: boolean; gmailConnected: boolean }) {
  const steps = [
    { done: hasGoals, icon: Target, title: "Pick the roles you want", href: "/welcome" },
    { done: hasResume, icon: FileText, title: "Upload your resume", href: "/profile" },
    { done: gmailConnected, icon: Mail, title: "Read LinkedIn & Naukri alerts", href: "/integrations" },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null;

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[15px] font-semibold text-fg">Finish setting up</div>
          <p className="mt-0.5 text-[13px] text-muted">{doneCount} of 3 done — each one makes your matches and resumes sharper.</p>
        </div>
        <Progress value={(doneCount / 3) * 100} tone="ok" className="w-40" />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {steps.map(({ done, icon: Icon, title, href }) => (
          <Link
            key={title}
            href={href}
            className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-[13px] transition-colors ${
              done ? "border-line text-subtle" : "border-line-strong bg-surface text-fg hover:bg-surface-hover"
            }`}
          >
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                done ? "bg-ok text-white" : "border border-line-strong text-muted"
              }`}
            >
              {done ? <Check size={13} strokeWidth={3} /> : <Icon size={12} />}
            </span>
            <span className={done ? "line-through decoration-line-strong" : "font-medium"}>{title}</span>
            {!done && <ArrowRight size={13} className="ml-auto text-subtle" />}
          </Link>
        ))}
      </div>
    </Card>
  );
}

function PicksForYou({ picks }: { picks: JobFeedItem[] | null }) {
  if (picks !== null && picks.length === 0) return null;
  return (
    <section>
      <SectionLabel
        action={
          <Link href="/jobs" className="group flex items-center gap-1 text-[13px] text-muted hover:text-fg">
            All jobs for you <ArrowRight size={13} className="transition-transform duration-300 group-hover:translate-x-0.5" />
          </Link>
        }
      >
        Picked for you today
      </SectionLabel>
      <div className="grid gap-3 sm:grid-cols-2">
        {picks === null
          ? [0, 1].map((i) => <div key={i} className="skeleton h-[92px]" />)
          : picks.map((job, i) => (
              <Reveal key={job.id} delay={i * 70}>
                <Link href="/jobs" className="card lift flex items-center gap-3 rounded-xl p-4">
                  <CompanyAvatar name={job.company} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-semibold text-fg">{job.title}</div>
                    <div className="truncate text-xs text-muted">
                      {job.company} · {job.location || (job.remote ? "Remote" : "")}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 text-xs font-semibold tabular-nums text-fg">
                    {job.match}%
                    <ArrowUpRight size={13} className="text-subtle" />
                  </div>
                </Link>
              </Reveal>
            ))}
      </div>
    </section>
  );
}

export default function DashboardPage() {
  const { user, profile, loading: authLoading } = useRequireAuth();
  const [data, setData] = useState<DashboardHomeOut | null>(null);
  const [picks, setPicks] = useState<JobFeedItem[] | null>(null);
  const [forwarding, setForwarding] = useState(false);
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
    api
      .alertAddress()
      .then((a) => setForwarding(a.activity.some((x) => x.kind === "job_alert")))
      .catch(() => {});
    api
      .jobFeed()
      .then((f) => setPicks(f.items.filter((j) => !j.tracked_application_id).slice(0, 4)))
      .catch(() => setPicks([]));
  }, [user]);

  if (authLoading || !user) return null;
  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!data) return <PageSkeleton />;

  const name = firstName(user);
  const gmailConnected = forwarding || integrations.some((i) => i.provider === "gmail" && i.status === "connected");
  const needsAttention = applications.filter((a) => ["READY_TO_APPLY", "MANUAL_APPLY_REQUIRED"].includes(currentStage(a) ?? ""));
  const appliedCount = applications.filter((a) => a.status_history.some((e) => e.stage === "APPLIED")).length;
  const interviewing = applications.filter((a) => ["OA", "INTERVIEW", "OFFER"].includes(currentStage(a) ?? "")).length;
  const nothingYet = data.recent_applications.length === 0;

  return (
    <div className="space-y-8">
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
              <Plus size={15} /> Add opportunity
            </Link>
          }
        />
      </div>

      <SetupChecklist
        hasGoals={Boolean(profile?.target_roles.length)}
        hasResume={data.has_resume}
        gmailConnected={gmailConnected}
      />

      <PicksForYou picks={picks} />

      {nothingYet ? (
        <EmptyState
          icon={Compass}
          title="Nothing tracked yet"
          description="Track a job from your picks, paste any job description, or let Gmail alerts flow in. Eligibility, skill gaps and a tailored resume follow automatically."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link href="/jobs" className={buttonClasses("primary", "md")}>
                <Compass size={15} /> Browse jobs for you
              </Link>
              <Link href="/opportunities" className={buttonClasses("secondary", "md")}>
                <Plus size={15} /> Paste a job
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="stagger grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard icon={Layers} value={<CountUp value={applications.length || data.recent_applications.length} />} label="Tracked" />
            <StatCard icon={Sparkles} value={<CountUp value={needsAttention.length} />} label="To review" tone={needsAttention.length ? "accent" : "neutral"} />
            <StatCard icon={Send} value={<CountUp value={appliedCount} />} label="Applied" />
            <StatCard icon={CalendarClock} value={<CountUp value={interviewing} />} label="In interviews" tone={interviewing ? "ok" : "neutral"} />
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            <div className="space-y-6">
              {needsAttention.length > 0 && (
                <section>
                  <SectionLabel
                    action={
                      <Link href="/applications" className="flex items-center gap-1 text-[13px] text-muted hover:text-fg">
                        View all <ArrowRight size={13} />
                      </Link>
                    }
                  >
                    Needs your attention
                  </SectionLabel>
                  <RowList>
                    {needsAttention.slice(0, 5).map((app) => (
                      <ApplicationRow key={app.id} app={app} />
                    ))}
                  </RowList>
                </section>
              )}
              <section>
                <SectionLabel
                  action={
                    <Link href="/opportunities" className="flex items-center gap-1 text-[13px] text-muted hover:text-fg">
                      All opportunities <ArrowRight size={13} />
                    </Link>
                  }
                >
                  Recently discovered
                </SectionLabel>
                <RowList>
                  {data.recent_applications.map((app) => (
                    <ApplicationRow key={app.id} app={app} />
                  ))}
                </RowList>
              </section>
            </div>

            <div className="space-y-6">
              <section>
                <SectionLabel>Closing soon</SectionLabel>
                <Card className="divide-y divide-line">
                  {data.urgent_deadlines.length === 0 ? (
                    <p className="p-4 text-[13px] text-muted">Nothing due in the next 14 days.</p>
                  ) : (
                    data.urgent_deadlines.map((app) => {
                      const days = daysUntil(app.deadline!);
                      return (
                        <Link key={app.id} href={`/applications/${app.id}`} className="flex items-center gap-3 p-3.5 transition-colors hover:bg-surface-2">
                          <CompanyAvatar name={app.company_name} size="sm" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-[13px] font-medium text-fg">{app.company_name}</div>
                            <div className="truncate text-xs text-muted">{app.role}</div>
                          </div>
                          <Badge tone={deadlineTone(days)}>{deadlineLabel(days)}</Badge>
                        </Link>
                      );
                    })
                  )}
                </Card>
              </section>

              <section>
                <SectionLabel>Skills to work on</SectionLabel>
                <Card className="p-4">
                  {data.most_common_missing_skills.length === 0 ? (
                    <p className="text-[13px] text-muted">No recurring gaps yet.</p>
                  ) : (
                    <ol className="space-y-2.5">
                      {data.most_common_missing_skills.map((skill, i) => (
                        <li key={skill} className="flex items-center gap-3 text-[13px]">
                          <span className="w-4 font-mono text-[11px] text-subtle">{i + 1}</span>
                          <span className="flex-1 font-medium text-fg">{skill}</span>
                          <Progress value={100 - i * 18} tone="neutral" className="w-20" />
                        </li>
                      ))}
                    </ol>
                  )}
                  <div className="mt-4 flex gap-6 border-t border-line pt-3 text-xs text-subtle">
                    <span>
                      <span className="font-semibold text-fg">{data.total_missing_skills}</span> missing
                    </span>
                    <span>
                      <span className="font-semibold text-fg">{data.total_weak_skills}</span> weak
                    </span>
                    <span className="ml-auto">across all roles</span>
                  </div>
                </Card>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
