import { Check } from "lucide-react";
import type { ApplicationStatusEvent } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  DISCOVERED: "Discovered",
  ELIGIBILITY_CHECKED: "Eligibility Checked",
  PREPARING: "Preparing",
  READY_TO_APPLY: "Ready to Apply",
  APPLIED: "Applied",
  OA: "Online Assessment",
  INTERVIEW: "Interview",
  OFFER: "Offer",
  REJECTED: "Rejected",
};

export function StatusTimeline({ history }: { history: ApplicationStatusEvent[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-slate-400">No status history yet.</p>;
  }

  return (
    <ol className="space-y-0">
      {history.map((event, i) => {
        const isLast = i === history.length - 1;
        return (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                  isLast ? "bg-indigo-600" : "bg-emerald-500"
                }`}
              >
                <Check size={13} className="text-white" strokeWidth={3} />
              </span>
              {!isLast && <span className="my-0.5 w-px flex-1 bg-slate-200" />}
            </div>
            <div className={`pb-5 ${isLast ? "" : ""}`}>
              <div className="pt-0.5 text-sm font-semibold text-slate-800">
                {STAGE_LABELS[event.stage] ?? event.stage}
              </div>
              <div className="text-xs text-slate-400">{new Date(event.created_at).toLocaleString()}</div>
              {event.note && <div className="mt-1 text-sm text-slate-600">{event.note}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
