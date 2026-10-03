import Link from "next/link";
import { ChevronRight, Globe2, Inbox } from "lucide-react";
import type { ApplicationOut } from "@/lib/types";
import { STAGE_META, currentStage, daysUntil, deadlineLabel, deadlineTone, isAlertSource } from "@/lib/stages";
import { Badge, CompanyAvatar } from "./ui";

/** One application as a row inside a bordered list (`divide-y`), Linear-style. */
export function ApplicationRow({ app, showStage = true }: { app: ApplicationOut; showStage?: boolean }) {
  const stage = currentStage(app);
  const meta = stage ? STAGE_META[stage] : null;
  const days = app.deadline ? daysUntil(app.deadline) : null;

  return (
    <Link
      href={`/applications/${app.id}`}
      className="group flex items-center gap-3.5 px-4 py-3 transition-colors hover:bg-surface-2"
    >
      <CompanyAvatar name={app.company_name} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[13.5px] font-medium text-fg">{app.role}</span>
          {isAlertSource(app.source) && <Inbox size={12} className="shrink-0 text-subtle" aria-label="From your job alerts" />}
          {app.source?.startsWith("web:") && <Globe2 size={12} className="shrink-0 text-subtle" aria-label="From a company job board" />}
        </div>
        <div className="truncate text-xs text-muted">{app.company_name}</div>
      </div>
      <div className="hidden shrink-0 items-center gap-2 sm:flex">
        {days !== null && days >= 0 && days <= 30 && <Badge tone={deadlineTone(days)}>{deadlineLabel(days)}</Badge>}
        {showStage && meta && (
          <Badge tone={meta.tone} dot>
            {meta.label}
          </Badge>
        )}
      </div>
      <ChevronRight size={15} className="shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  );
}

/** Bordered container for ApplicationRow lists. */
export function RowList({ children }: { children: React.ReactNode }) {
  return <div className="card divide-y divide-line overflow-hidden rounded-xl">{children}</div>;
}
