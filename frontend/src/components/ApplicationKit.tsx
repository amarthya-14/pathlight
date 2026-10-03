"use client";

import { useEffect, useState } from "react";
import { Check, ChevronDown, ClipboardCopy, ExternalLink, ListChecks, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ApplicationKit } from "@/lib/types";
import { Card, cx, Skeleton } from "./ui";

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // clipboard blocked — the text is selectable on screen
        }
      }}
      className={cx(
        "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border px-2 text-xs font-medium transition-colors duration-200",
        copied ? "border-ok/30 bg-ok-soft text-ok" : "border-line-strong bg-surface text-muted hover:text-fg"
      )}
      aria-label={`${label}: ${text.slice(0, 40)}`}
    >
      {copied ? <Check size={12} strokeWidth={2.6} /> : <ClipboardCopy size={12} />}
      {copied ? "Copied" : label}
    </button>
  );
}

function Section({
  open,
  onToggle,
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  icon: typeof ListChecks;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-line first:border-t-0">
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-surface-2"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2">
          <Icon size={15} className="text-fg" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] font-semibold text-fg">{title}</span>
          <span className="block text-xs text-muted">{subtitle}</span>
        </span>
        <ChevronDown size={16} className={cx("shrink-0 text-subtle transition-transform duration-300", open && "rotate-180")} />
      </button>
      <div
        className={cx("grid transition-[grid-template-rows,opacity] duration-500", open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0")}
        style={{ transitionTimingFunction: "var(--ease-out)" }}
      >
        {/* inert while collapsed: hidden buttons must not be reachable by keyboard. */}
        <div className="overflow-hidden" inert={!open}>
          {children}
        </div>
      </div>
    </div>
  );
}

// Ready-to-paste answers for the application form (LinkedIn Easy Apply screening
// questions, Workday/Greenhouse fields) and a referral helper. Everything comes from the
// resume and profile, with a note explaining each number — never a guess.
export function ApplicationKitPanel({ applicationId, site }: { applicationId: string; site: string }) {
  const [kit, setKit] = useState<ApplicationKit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<"answers" | "referral" | null>("answers");

  useEffect(() => {
    api
      .applicationKit(applicationId)
      .then(setKit)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load the application kit"));
  }, [applicationId]);

  if (error) return null;

  return (
    <Card className="overflow-hidden">
      <Section
        open={open === "answers"}
        onToggle={() => setOpen(open === "answers" ? null : "answers")}
        icon={ListChecks}
        title="Answers for the application form"
        subtitle={`For ${site}'s screening questions — honest numbers, worked out from your resume.`}
      >
        {kit === null ? (
          <div className="space-y-2 px-5 pb-5">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : (
          <ul className="divide-y divide-line border-t border-line">
            {kit.answers.map((a) => (
              <li key={a.question} className="flex items-start gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-subtle">{a.question}</div>
                  <div className="mt-0.5 break-words text-[13.5px] font-medium text-fg">{a.answer}</div>
                  {a.note && <div className="mt-1 text-xs leading-relaxed text-muted">{a.note}</div>}
                </div>
                <CopyButton text={a.answer} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        open={open === "referral"}
        onToggle={() => setOpen(open === "referral" ? null : "referral")}
        icon={Users}
        title="Ask for a referral"
        subtitle="Referrals get read first. Alumni are the warmest people to ask."
      >
        {kit && (
          <div className="space-y-4 border-t border-line px-5 py-4">
            <div className="flex flex-wrap gap-2">
              {kit.search_links.map((l) => (
                <a
                  key={l.url}
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 text-[12.5px] font-medium text-fg transition-colors hover:bg-surface-hover"
                >
                  <ExternalLink size={12} /> {l.label}
                </a>
              ))}
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-medium text-fg">Connection note · {kit.connection_note.length}/300</span>
                <CopyButton text={kit.connection_note} />
              </div>
              <p className="rounded-lg bg-surface-2 px-3 py-2.5 text-[13px] leading-relaxed text-muted">{kit.connection_note}</p>
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-medium text-fg">Message after they accept</span>
                <CopyButton text={kit.referral_message} />
              </div>
              <p className="whitespace-pre-wrap rounded-lg bg-surface-2 px-3 py-2.5 text-[13px] leading-relaxed text-muted">
                {kit.referral_message}
              </p>
            </div>
          </div>
        )}
      </Section>
    </Card>
  );
}
