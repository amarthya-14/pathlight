"use client";

import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Check,
  FileText,
  Inbox,
  Lock,
  MousePointerClick,
  Radar,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  TriangleAlert,
  Wand2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Brand } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge, buttonClasses, CompanyAvatar } from "@/components/ui";

// Public landing page — what a friend sees when you share the link. Signed-in users
// see the same page with "Open dashboard" in place of the sign-up calls to action.

const PIPELINE = [
  { icon: Inbox, title: "Discover", text: "Reads LinkedIn & Naukri job alerts from your Gmail — or paste any JD." },
  { icon: BadgeCheck, title: "Check eligibility", text: "CGPA, branch and criteria checked with evidence, never a bare verdict." },
  { icon: ScanSearch, title: "Find skill gaps", text: "Your resume + GitHub vs. the role: matched, weak, missing." },
  { icon: Wand2, title: "Tailor", text: "A resume and cover note tuned for this role — reworded, never invented." },
  { icon: MousePointerClick, title: "You approve", text: "Nothing is sent until you say so. One click to apply." },
];

const FEATURES = [
  {
    icon: Radar,
    title: "Opportunities find you",
    text: "Connect Gmail once. Every job alert is parsed, de-duplicated and lined up for you — automatically.",
    className: "md:col-span-2",
  },
  {
    icon: ShieldCheck,
    title: "Honest by design",
    text: "A code-level guard rejects any tailored resume that claims a skill you don't have.",
    className: "",
  },
  {
    icon: Target,
    title: "Know where you stand",
    text: "Eligibility with reasons and confidence, skill gaps backed by your own resume and GitHub repos.",
    className: "",
  },
  {
    icon: BookOpenCheck,
    title: "A plan before the deadline",
    text: "Missing skills become an ordered prep plan — prerequisites first, hours estimated, feasibility checked against the deadline.",
    className: "md:col-span-2",
  },
];

function HeroMock() {
  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      <div className="absolute -inset-8 rounded-[40px] bg-gradient-to-tr from-violet-600/30 via-indigo-500/20 to-cyan-400/30 blur-3xl" />

      <div className="glass glow-border relative rounded-3xl p-5 shadow-card-lg sm:p-6">
        <div className="flex items-center gap-3">
          <CompanyAvatar name="Aptora Labs" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-fg">Spring Boot Developer</div>
            <div className="text-xs text-muted">Aptora Labs · via LinkedIn alert</div>
          </div>
          <Badge tone="ok" dot>
            Eligible
          </Badge>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-2.5 text-center">
          {[
            ["92%", "Match"],
            ["8.55", "Your CGPA"],
            ["6d", "Deadline"],
          ].map(([v, l]) => (
            <div key={l} className="rounded-xl border border-line bg-surface-2 py-2.5">
              <div className="text-base font-semibold text-fg">{v}</div>
              <div className="text-[10px] uppercase tracking-wider text-subtle">{l}</div>
            </div>
          ))}
        </div>

        <div className="mt-5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">Skill gap</div>
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="ok" dot>Java</Badge>
            <Badge tone="ok" dot>Spring Boot</Badge>
            <Badge tone="ok" dot>REST APIs</Badge>
            <Badge tone="warn" dot>Docker</Badge>
            <Badge tone="bad" dot>Kubernetes</Badge>
          </div>
        </div>

        <div className="mt-5 rounded-2xl border border-line bg-surface-2 p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-fg">
            <Sparkles size={14} className="text-accent-fg" /> Tailored resume ready
          </div>
          <div className="mt-2 space-y-1.5 font-mono text-[11px] leading-relaxed">
            <div className="rounded-md bg-bad-soft px-2 py-0.5 text-bad line-through decoration-bad/40">− Built REST endpoints</div>
            <div className="rounded-md bg-ok-soft px-2 py-0.5 text-ok">+ Built Spring Boot REST APIs for order tracking</div>
          </div>
        </div>

        <div className="mt-5 flex gap-2">
          <span className={buttonClasses("primary", "md", "flex-1 pointer-events-none")}>
            Apply on LinkedIn <ArrowRight size={15} />
          </span>
          <span className={buttonClasses("secondary", "md", "pointer-events-none")}>Skip</span>
        </div>
      </div>

      <div className="animate-float absolute -left-10 -top-9 hidden items-center gap-2.5 rounded-2xl border border-line-strong bg-bg-elevated px-3.5 py-2.5 text-xs shadow-card-lg sm:flex" style={{ animationDelay: "-2s" }}>
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-info-soft text-info">
          <Inbox size={14} />
        </span>
        <div>
          <div className="font-semibold text-fg">3 new job alerts</div>
          <div className="text-subtle">from LinkedIn · just now</div>
        </div>
      </div>

      <div className="animate-float absolute -bottom-14 -right-8 hidden max-w-[250px] items-start gap-2.5 rounded-2xl border border-line-strong bg-bg-elevated px-3.5 py-2.5 text-xs shadow-card-lg sm:flex">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-warn-soft text-warn">
          <TriangleAlert size={14} />
        </span>
        <div>
          <div className="font-semibold text-fg">Kubernetes not added</div>
          <div className="text-subtle">It&apos;s not on your resume — we never invent skills.</div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { user } = useAuth();
  const primaryCta = user
    ? { href: "/dashboard", label: "Open your dashboard" }
    : { href: "/register", label: "Get started — it's free" };

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <header className="sticky top-0 z-40 px-3 pt-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between rounded-2xl border border-line bg-bg-elevated/75 px-4 py-2.5 shadow-card backdrop-blur-xl sm:px-5">
          <Brand />
          <nav className="hidden items-center gap-7 text-sm text-muted md:flex">
            <a href="#how" className="transition-colors hover:text-fg">How it works</a>
            <a href="#features" className="transition-colors hover:text-fg">Features</a>
            <a href="#trust" className="transition-colors hover:text-fg">Trust</a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {!user && (
              <Link href="/login" className={buttonClasses("ghost", "sm", "hidden sm:inline-flex h-9")}>
                Log in
              </Link>
            )}
            <Link href={primaryCta.href} className={buttonClasses("primary", "sm", "h-9")}>
              {user ? "Dashboard" : "Sign up"} <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-20 px-5 pb-24 pt-16 sm:pt-24 lg:grid-cols-[1.15fr_1fr] lg:gap-12 lg:pt-28">
        <div className="stagger text-center lg:text-left">
          <div className="flex justify-center lg:justify-start">
            <span className="glass inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium text-muted">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-ok" />
              </span>
              Built for campus placements · Free for students
            </span>
          </div>
          <h1 className="mt-6 text-[2.5rem] font-semibold leading-[1.04] tracking-[-0.04em] text-fg sm:text-[3.4rem] lg:text-[3.25rem] xl:text-[3.7rem]">
            <span className="whitespace-nowrap">Placement season,</span>
            <br />
            <span className="animated-gradient-text">on autopilot.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg lg:mx-0">
            Pathlight reads your job alerts, checks eligibility, finds your skill gaps and tailors your resume for every
            role — then applies <span className="font-medium text-fg">only when you say so</span>.
          </p>
          <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
            <Link href={primaryCta.href} className={buttonClasses("primary", "lg", "w-full sm:w-auto")}>
              {primaryCta.label} <ArrowRight size={17} />
            </Link>
            <a href="#how" className={buttonClasses("secondary", "lg", "w-full sm:w-auto")}>
              See how it works
            </a>
          </div>
          <div className="mt-9 flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs text-muted lg:justify-start">
            {["Never invents skills", "You approve every application", "Encrypted Gmail access"].map((t) => (
              <span key={t} className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-ok" strokeWidth={2.6} /> {t}
              </span>
            ))}
          </div>
        </div>

        <div className="animate-fade-up px-4 sm:px-8 lg:px-0" style={{ animationDelay: "0.25s" }}>
          <HeroMock />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-fg">How it works</div>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
            From job alert to application in <span className="text-gradient">five steps</span>
          </h2>
          <p className="mt-4 text-muted">
            Five specialised AI agents work in sequence. Every decision shows its evidence, and the last step is always
            yours.
          </p>
        </div>

        <div className="relative mt-14">
          <div className="travel-line absolute left-[10%] right-[10%] top-7 hidden h-px bg-line-strong md:block" />
          <ol className="stagger relative grid gap-5 md:grid-cols-5">
            {PIPELINE.map((step, i) => {
              const Icon = step.icon;
              const last = i === PIPELINE.length - 1;
              return (
                <li key={step.title} className="flex gap-4 md:flex-col md:items-center md:text-center">
                  <div
                    className={`relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border ${
                      last
                        ? "border-transparent bg-brand-gradient text-white shadow-glow"
                        : "border-line bg-surface-solid text-accent-fg"
                    }`}
                  >
                    <Icon size={22} strokeWidth={1.9} />
                    <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-line bg-bg-elevated text-[10px] font-semibold text-muted">
                      {i + 1}
                    </span>
                  </div>
                  <div>
                    <div className="font-semibold text-fg md:mt-4">{step.title}</div>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{step.text}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20">
        <div className="max-w-2xl">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-fg">Features</div>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
            Everything a placement season needs. <span className="text-muted">Nothing it doesn&apos;t.</span>
          </h2>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className={`glass group relative overflow-hidden rounded-3xl p-7 transition-all duration-300 hover:-translate-y-1 hover:border-line-strong ${f.className}`}
              >
                <div className="absolute -right-16 -top-16 h-40 w-40 rounded-full bg-accent/20 opacity-0 blur-3xl transition-opacity duration-500 group-hover:opacity-100" />
                <div className="relative">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent-fg">
                    <Icon size={20} />
                  </div>
                  <h3 className="mt-5 text-lg font-semibold text-fg">{f.title}</h3>
                  <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">{f.text}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Trust */}
      <section id="trust" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20">
        <div className="glass glow-border relative overflow-hidden rounded-[2rem] p-8 sm:p-12">
          <div className="absolute -left-20 -top-24 h-72 w-72 rounded-full bg-violet-600/25 blur-3xl" />
          <div className="absolute -bottom-24 right-0 h-72 w-72 rounded-full bg-cyan-500/20 blur-3xl" />
          <div className="relative grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:items-center">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-fg">Trust</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
                An AI that works for you — <span className="text-gradient">and tells you the truth.</span>
              </h2>
              <p className="mt-4 max-w-lg leading-relaxed text-muted">
                Autopilot doesn&apos;t mean out of control. Pathlight is built so the important calls stay with you, and
                the AI can&apos;t quietly embellish who you are.
              </p>
            </div>
            <ul className="space-y-3">
              {[
                { icon: ShieldCheck, t: "Never fabricates", d: "Tailoring is checked in code — a resume claiming a skill you don't have is rejected." },
                { icon: MousePointerClick, t: "Nothing sent without you", d: "Every application waits for your explicit approval, with the exact email shown first." },
                { icon: Lock, t: "Your Gmail stays yours", d: "Read-only for alerts, send only on approval, tokens encrypted at rest, revocable anytime." },
                { icon: FileText, t: "Evidence, not verdicts", d: "Every decision shows its reasons, evidence and confidence." },
              ].map(({ icon: Icon, t, d }) => (
                <li key={t} className="flex gap-3.5 rounded-2xl border border-line bg-surface-2 p-4">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-ok">
                    <Icon size={17} />
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-fg">{t}</div>
                    <div className="mt-0.5 text-sm leading-relaxed text-muted">{d}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-4xl px-5 pb-24 pt-10 text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-fg sm:text-5xl">
          Stop refreshing job boards.
          <br />
          <span className="text-gradient">Start getting shortlisted.</span>
        </h2>
        <p className="mx-auto mt-5 max-w-lg text-muted">
          Set up in two minutes: add your CGPA, upload your resume, connect Gmail. Pathlight takes it from there.
        </p>
        <Link href={primaryCta.href} className={buttonClasses("primary", "lg", "mt-9")}>
          {primaryCta.label} <ArrowRight size={17} />
        </Link>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 text-sm text-subtle sm:flex-row">
          <Brand />
          <p>Made for students, by a student. Your data is never sold or shared.</p>
        </div>
      </footer>
    </div>
  );
}
