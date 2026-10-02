"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { BookOpenCheck, Check, ChevronRight, Clock } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PreparationPlanOut, PreparationTaskOut, TaskStatus } from "@/lib/types";
import { useToast } from "@/components/Toast";
import { Alert, Button, Card, EmptyState, PageHeader, PageSkeleton, Progress, SectionLabel } from "@/components/ui";

function TaskRow({
  task,
  allTasks,
  onToggle,
  busy,
}: {
  task: PreparationTaskOut;
  allTasks: PreparationTaskOut[];
  onToggle: () => void;
  busy: boolean;
}) {
  const depNames = task.depends_on.map((id) => allTasks.find((t) => t.id === id)?.skill).filter((s): s is string => Boolean(s));
  const done = task.status === "done";
  const blockedBy = task.depends_on
    .map((id) => allTasks.find((t) => t.id === id))
    .filter((t): t is PreparationTaskOut => Boolean(t) && t!.status !== "done");

  return (
    <li className="flex items-start gap-3.5 px-4 py-3.5">
      <button
        onClick={onToggle}
        disabled={busy}
        aria-label={done ? `Mark ${task.title} as not done` : `Mark ${task.title} as done`}
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
          done ? "border-ok bg-ok text-white" : "border-line-strong bg-surface hover:border-fg"
        }`}
      >
        {done && <Check size={13} strokeWidth={3} />}
      </button>
      <div className="min-w-0 flex-1">
        <div className={`text-[13.5px] font-medium ${done ? "text-subtle line-through decoration-line-strong" : "text-fg"}`}>{task.title}</div>
        <div className="mt-0.5 text-[13px] leading-relaxed text-muted">{task.description}</div>
        {depNames.length > 0 && (
          <div className="mt-1.5 text-xs text-subtle">
            After {depNames.join(", ")}
            {!done && blockedBy.length > 0 && <span className="text-warn"> · start with {blockedBy.map((t) => t.skill).join(", ")} first</span>}
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1 text-[13px] tabular-nums text-muted">
        <Clock size={12} className="text-subtle" />
        {task.estimated_hours}h
      </div>
    </li>
  );
}

export default function PreparationPlanPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const toast = useToast();
  const params = useParams<{ id: string }>();
  const [plan, setPlan] = useState<PreparationPlanOut | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [regenerating, setRegenerating] = useState(false);
  const [busyTask, setBusyTask] = useState<string | null>(null);

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
      toast("Plan recalculated", { description: `Based on ${hoursPerDay}h of study a day.` });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to regenerate plan");
    } finally {
      setRegenerating(false);
    }
  };

  const toggleTask = async (task: PreparationTaskOut) => {
    const next: TaskStatus = task.status === "done" ? "not_started" : "done";
    setBusyTask(task.id);
    // Optimistic: tick immediately, roll back if the save fails.
    setPlan((p) => (p ? { ...p, tasks: p.tasks.map((t) => (t.id === task.id ? { ...t, status: next } : t)) } : p));
    try {
      setPlan(await api.updateTaskStatus(params.id, task.id, next));
    } catch {
      setPlan((p) => (p ? { ...p, tasks: p.tasks.map((t) => (t.id === task.id ? { ...t, status: task.status } : t)) } : p));
      toast("Couldn't save that", { tone: "bad" });
    } finally {
      setBusyTask(null);
    }
  };

  if (authLoading || !user) return null;
  if (!loaded) return <PageSkeleton />;

  const tasks = plan ? [...plan.tasks].sort((a, b) => a.order_index - b.order_index) : [];
  const doneHours = tasks.filter((t) => t.status === "done").reduce((s, t) => s + t.estimated_hours, 0);
  const totalHours = plan?.total_estimated_hours ?? 0;
  const progress = totalHours ? Math.round((doneHours / totalHours) * 100) : 0;
  const load = plan && plan.available_hours ? Math.round((plan.total_estimated_hours / Math.max(plan.available_hours, 0.1)) * 100) : null;

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1.5 text-[13px] text-subtle">
        <Link href="/applications" className="hover:text-fg">
          Applications
        </Link>
        <ChevronRight size={13} />
        <Link href={`/applications/${params.id}`} className="hover:text-fg">
          Application
        </Link>
        <ChevronRight size={13} />
        <span className="text-muted">Prep plan</span>
      </nav>

      <div className="animate-fade-in">
        <PageHeader
          title="Preparation plan"
          subtitle="Your skill gaps as an ordered checklist — prerequisites first, with time estimates checked against the deadline."
        />
      </div>

      {error && <Alert tone="bad">{error}</Alert>}

      {notFound && !plan && (
        <EmptyState
          icon={BookOpenCheck}
          title="No plan yet"
          description="Either there's nothing missing to prepare for (good news), or a plan hasn't been generated with your real study time. Set your hours below and generate one."
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0 space-y-6">
          {plan && (
            <section>
              <SectionLabel action={<span className="text-xs tabular-nums text-subtle">{tasks.filter((t) => t.status === "done").length} / {tasks.length} done</span>}>
                Steps, in order
              </SectionLabel>
              <Card className="overflow-hidden">
                <div className="border-b border-line px-4 py-3">
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="text-muted">
                      <span className="font-semibold text-fg">{doneHours}h</span> of {totalHours}h complete
                    </span>
                    <span className="tabular-nums text-subtle">{progress}%</span>
                  </div>
                  <Progress value={progress} tone="ok" className="mt-2" />
                </div>
                <ol className="divide-y divide-line">
                  {tasks.map((task) => (
                    <TaskRow key={task.id} task={task} allTasks={plan.tasks} onToggle={() => toggleTask(task)} busy={busyTask === task.id} />
                  ))}
                </ol>
              </Card>
            </section>
          )}
        </div>

        <aside className="space-y-4">
          <Card className="p-4">
            <form onSubmit={onRegenerate}>
              <div className="flex items-center justify-between">
                <label htmlFor="hours" className="text-[13px] font-medium text-fg">
                  Study time per day
                </label>
                <span className="text-[13px] font-semibold tabular-nums text-fg">{hoursPerDay}h</span>
              </div>
              <input
                id="hours"
                type="range"
                min={0.5}
                max={10}
                step={0.5}
                value={hoursPerDay}
                onChange={(e) => setHoursPerDay(Number(e.target.value))}
                className="mt-4 w-full"
              />
              <div className="mt-1.5 flex justify-between text-[11px] text-subtle">
                <span>30 min</span>
                <span>10 h</span>
              </div>
              <Button type="submit" loading={regenerating} className="mt-4 w-full">
                {regenerating ? "Planning…" : plan ? "Recalculate plan" : "Generate plan"}
              </Button>
              {plan && <p className="mt-2 text-[11px] leading-relaxed text-subtle">Recalculating creates a fresh plan and resets ticked tasks.</p>}
            </form>
          </Card>

          {plan && (
            <Card className="p-4">
              <div className="text-[13px] font-medium text-fg">Will you make the deadline?</div>
              <div
                className={`mt-2 text-xl font-semibold tracking-tight ${
                  plan.feasible === null ? "text-fg" : plan.feasible ? "text-ok" : "text-bad"
                }`}
              >
                {plan.feasible === null ? "No deadline set" : plan.feasible ? "Yes, on track" : "It's tight"}
              </div>
              <dl className="mt-3 space-y-2 text-[13px]">
                <div className="flex justify-between">
                  <dt className="text-subtle">Study needed</dt>
                  <dd className="tabular-nums text-fg">{plan.total_estimated_hours}h</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-subtle">Time available</dt>
                  <dd className="tabular-nums text-fg">{plan.available_hours !== null ? `${plan.available_hours}h` : "—"}</dd>
                </div>
              </dl>
              {load !== null && (
                <>
                  <Progress value={load} tone={plan.feasible ? "ok" : "bad"} className="mt-3" />
                  <div className="mt-1.5 text-[11px] text-subtle">{load}% of your available time</div>
                </>
              )}
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
