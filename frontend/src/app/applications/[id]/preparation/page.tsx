"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BookOpenCheck, CalendarClock, CheckCircle2, Clock, GitBranch, Hourglass, RotateCw } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PreparationPlanOut, PreparationTaskOut } from "@/lib/types";
import { Alert, Button, Card, EmptyState, PageHeader, PageSkeleton, SectionLabel, StatCard } from "@/components/ui";

function TaskStep({ task, allTasks, last }: { task: PreparationTaskOut; allTasks: PreparationTaskOut[]; last: boolean }) {
  const depNames = task.depends_on
    .map((id) => allTasks.find((t) => t.id === id)?.skill)
    .filter((s): s is string => Boolean(s));
  const done = task.status === "done";

  return (
    <li className="relative flex gap-4 pb-4 last:pb-0">
      {!last && <span className="absolute left-[19px] top-11 h-[calc(100%-2.25rem)] w-px bg-gradient-to-b from-accent/50 to-line" />}
      <span
        className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-semibold ${
          done ? "bg-ok text-white" : "border border-line bg-surface-solid text-accent-fg"
        }`}
      >
        {done ? <CheckCircle2 size={18} /> : task.order_index + 1}
      </span>
      <Card interactive className="min-w-0 flex-1 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-semibold text-fg">{task.title}</div>
            <div className="mt-1 text-sm leading-relaxed text-muted">{task.description}</div>
          </div>
          <div className="shrink-0 rounded-lg bg-surface-2 px-2.5 py-1 text-right">
            <div className="flex items-center gap-1 text-sm font-semibold tabular-nums text-fg">
              <Clock size={12} className="text-subtle" />
              {task.estimated_hours}h
            </div>
          </div>
        </div>
        {depNames.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-subtle">
            <GitBranch size={12} /> After:
            {depNames.map((d) => (
              <span key={d} className="rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent-fg">
                {d}
              </span>
            ))}
          </div>
        )}
      </Card>
    </li>
  );
}

export default function PreparationPlanPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const [plan, setPlan] = useState<PreparationPlanOut | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    if (!user) return;
    api
      .getPreparationPlan(params.id)
      .then((p) => {
        setPlan(p);
        setNotFound(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setError(err instanceof ApiError ? err.detail : "Failed to load plan");
      })
      .finally(() => setLoaded(true));
  }, [user, params.id]);

  const onRegenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegenerating(true);
    setError(null);
    try {
      setPlan(await api.regeneratePreparationPlan(params.id, hoursPerDay));
      setNotFound(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to regenerate plan");
    } finally {
      setRegenerating(false);
    }
  };

  if (authLoading || !user) return null;
  if (!loaded) return <PageSkeleton />;

  const tasks = plan ? [...plan.tasks].sort((a, b) => a.order_index - b.order_index) : [];
  const usage =
    plan && plan.available_hours ? Math.round((plan.total_estimated_hours / Math.max(plan.available_hours, 0.1)) * 100) : null;

  return (
    <div className="space-y-8">
      <Link href={`/applications/${params.id}`} className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-fg">
        <ArrowLeft size={15} /> Back to application
      </Link>

      <div className="animate-fade-in">
        <PageHeader
          eyebrow="Prepare"
          title="Preparation plan"
          subtitle="Your skill gaps turned into an ordered plan — prerequisites first, with time estimates checked against the deadline."
        />
      </div>

      <Card className="p-5 sm:p-6">
        <form onSubmit={onRegenerate} className="flex flex-col gap-5 sm:flex-row sm:items-end">
          <div className="flex-1">
            <div className="mb-3 flex items-center justify-between">
              <label htmlFor="hours" className="text-sm font-medium text-fg">
                Hours you can study per day
              </label>
              <span className="rounded-lg bg-accent-soft px-2.5 py-1 text-sm font-semibold tabular-nums text-accent-fg">
                {hoursPerDay}h / day
              </span>
            </div>
            <input
              id="hours"
              type="range"
              min={0.5}
              max={10}
              step={0.5}
              value={hoursPerDay}
              onChange={(e) => setHoursPerDay(Number(e.target.value))}
              className="w-full accent-violet-500"
            />
            <div className="mt-1 flex justify-between text-[10px] text-subtle">
              <span>30 min</span>
              <span>10 h</span>
            </div>
          </div>
          <Button type="submit" size="lg" loading={regenerating}>
            {!regenerating && <RotateCw size={15} />}
            {regenerating ? "Planning…" : plan ? "Recalculate plan" : "Generate plan"}
          </Button>
        </form>
      </Card>

      {error && <Alert tone="bad">{error}</Alert>}

      {notFound && !plan && (
        <EmptyState
          icon={BookOpenCheck}
          title="No plan yet"
          description="Either there are no missing or weak skills to prepare for (good news!), or a plan hasn't been generated with your real study time. Set your hours above and generate one."
        />
      )}

      {plan && (
        <>
          <div className="stagger grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
            <StatCard icon={Hourglass} value={`${plan.total_estimated_hours}h`} label="Total study time" />
            <StatCard
              icon={CalendarClock}
              value={plan.available_hours !== null ? `${plan.available_hours}h` : "—"}
              label="Available before deadline"
            />
            <div className="col-span-2 lg:col-span-1">
              <StatCard
                icon={CheckCircle2}
                value={plan.feasible === null ? "Unknown" : plan.feasible ? "On track" : "Tight"}
                label={plan.feasible === null ? "No deadline to compare against" : plan.feasible ? "You can finish in time" : "More hours than you have"}
                tone={plan.feasible === null ? "neutral" : plan.feasible ? "success" : "danger"}
              />
            </div>
          </div>

          {usage !== null && (
            <Card className="p-5">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium text-fg">Study load vs. time available</span>
                <span className={`font-semibold tabular-nums ${plan.feasible ? "text-ok" : "text-bad"}`}>{usage}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    plan.feasible ? "bg-gradient-to-r from-emerald-400 to-cyan-400" : "bg-gradient-to-r from-amber-400 to-rose-500"
                  }`}
                  style={{ width: `${Math.min(usage, 100)}%` }}
                />
              </div>
            </Card>
          )}

          <section>
            <SectionLabel>{tasks.length} steps, in order</SectionLabel>
            <ol className="stagger">
              {tasks.map((task, i) => (
                <TaskStep key={task.id} task={task} allTasks={plan.tasks} last={i === tasks.length - 1} />
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
