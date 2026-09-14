"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CalendarClock, CheckCircle2, GitBranch, Hourglass, RotateCw } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PreparationPlanOut, PreparationTaskOut } from "@/lib/types";
import { Button, Field, PageHeader, StatCard, TextInput } from "@/components/ui";

function TaskRow({ task, allTasks }: { task: PreparationTaskOut; allTasks: PreparationTaskOut[] }) {
  const depNames = task.depends_on
    .map((id) => allTasks.find((t) => t.id === id)?.skill)
    .filter((s): s is string => Boolean(s));

  return (
    <div className="card-shadow card-shadow-hover flex items-start justify-between rounded-xl border border-slate-200 bg-white p-4 transition-all">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-600">
          {task.order_index + 1}
        </div>
        <div>
          <div className="font-semibold text-slate-800">{task.title}</div>
          <div className="mt-0.5 text-sm text-slate-500">{task.description}</div>
          {depNames.length > 0 && (
            <div className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-400">
              <GitBranch size={12} /> Depends on: {depNames.join(", ")}
            </div>
          )}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-sm font-semibold text-slate-800">{task.estimated_hours}h</div>
        <div className="text-xs capitalize text-slate-400">{task.status.replace("_", " ")}</div>
      </div>
    </div>
  );
}

export default function PreparationPlanPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const [plan, setPlan] = useState<PreparationPlanOut | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [regenerating, setRegenerating] = useState(false);

  const load = () => {
    api
      .getPreparationPlan(params.id)
      .then((p) => {
        setPlan(p);
        setNotFound(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof ApiError ? err.detail : "Failed to load plan");
        }
      });
  };

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, params.id]);

  const onRegenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegenerating(true);
    setError(null);
    try {
      const p = await api.regeneratePreparationPlan(params.id, hoursPerDay);
      setPlan(p);
      setNotFound(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to regenerate plan");
    } finally {
      setRegenerating(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="animate-fade-in space-y-8">
      <PageHeader title="Preparation Plan" subtitle="An ordered task list for closing your skill gaps before the deadline." />

      <form onSubmit={onRegenerate} className="card-shadow flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="w-40">
          <Field label="Hours/day available">
            <TextInput
              type="number"
              min={0.5}
              step={0.5}
              value={hoursPerDay}
              onChange={(e) => setHoursPerDay(Number(e.target.value))}
            />
          </Field>
        </div>
        <Button type="submit" disabled={regenerating}>
          {regenerating ? "Generating…" : plan ? "Regenerate plan" : "Generate plan"}
          {!regenerating && <RotateCw size={15} />}
        </Button>
      </form>

      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}

      {notFound && !plan && (
        <p className="text-sm text-slate-500">
          No preparation plan yet. This means either the pipeline hasn&apos;t auto-generated one (no missing/weak
          skills to prepare for — good news!), or you haven&apos;t generated one with your real available hours yet.
          Enter your hours/day above and generate one.
        </p>
      )}

      {plan && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <StatCard icon={Hourglass} value={`${plan.total_estimated_hours}h`} label="Total estimated" />
            <StatCard
              icon={CalendarClock}
              value={plan.available_hours !== null ? `${plan.available_hours}h` : "—"}
              label="Available before deadline"
            />
            <StatCard
              icon={CheckCircle2}
              value={plan.feasible === null ? "Unknown" : plan.feasible ? "Feasible" : "Not feasible"}
              label={plan.feasible === null ? "no deadline set" : "given available hours"}
              tone={plan.feasible === null ? "neutral" : plan.feasible ? "success" : "danger"}
            />
          </div>

          <div className="space-y-2.5">
            {[...plan.tasks]
              .sort((a, b) => a.order_index - b.order_index)
              .map((task) => (
                <TaskRow key={task.id} task={task} allTasks={plan.tasks} />
              ))}
          </div>
        </>
      )}
    </div>
  );
}
