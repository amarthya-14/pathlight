import Link from "next/link";
import { ChevronRight, Inbox } from "lucide-react";
import type { ApplicationOut } from "@/lib/types";
import { STAGE_META, currentStage, daysUntil, deadlineLabel, deadlineTone } from "@/lib/stages";
import { Badge, CompanyAvatar } from "./ui";

export function ApplicationRow({ app, showStage = true }: { app: ApplicationOut; showStage?: boolean }) {
  const stage = currentStage(app);
  const meta = stage ? STAGE_META[stage] : null;
  const days = app.deadline ? daysUntil(app.deadline) : null;

  return (
    <Link
      href={`/applications/${app.id}`}
      className="glass group flex items-center gap-3.5 rounded-2xl px-4 py-3.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-surface-hover"
    >
      <CompanyAvatar name={app.company_name} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-fg">{app.role}</span>
          {app.source === "gmail_mcp" && (
            <Inbox size={13} className="shrink-0 text-info" aria-label="Found in your Gmail job alerts" />
          )}
        </div>
        <div className="truncate text-xs text-muted">{app.company_name}</div>
      </div>
      <div className="hidden shrink-0 items-center gap-2 sm:flex">
        {days !== null && <Badge tone={deadlineTone(days)}>{deadlineLabel(days)}</Badge>}
        {showStage && meta && (
          <Badge tone={meta.tone} dot>
            {meta.label}
          </Badge>
        )}
      </div>
      <ChevronRight size={16} className="shrink-0 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-fg" />
    </Link>
  );
}
