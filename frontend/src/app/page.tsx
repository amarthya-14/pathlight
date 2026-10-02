"use client";

import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Check,
  ChevronDown,
  ExternalLink,
  FileText,
  Inbox,
  Lock,
  Mail,
  MousePointerClick,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Wand2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Brand, BrandMark } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge, buttonClasses, CompanyAvatar } from "@/components/ui";

// Public landing page — what a friend sees when you share the link. Signed-in users
// see the same page with "Open dashboard" in place of the sign-up calls to action.

const STEPS = [
  { icon: Inbox, title: "Discover", text: "Reads LinkedIn & Naukri job alerts from your Gmail — or paste any job description." },
  { icon: BadgeCheck, title: "Check eligibility", text: "CGPA, branch and experience checked with evidence. Unclear? It says so." },
  { icon: ScanSearch, title: "Find skill gaps", text: "Your resume and GitHub against the role: matched, weak, missing." },
  { icon: Wand2, title: "Tailor", text: "A resume and cover note for this role — reworded, never invented." },
  { icon: MousePointerClick, title: "You approve", text: "Nothing goes out until you say so. Then it's one click." },
];

const FEATURES = [
  { icon: Inbox, title: "Opportunities find you", text: "Connect Gmail once. Every job alert is parsed, de-duplicated and lined up for review." },
  { icon: BadgeCheck, title: "Honest eligibility", text: "Hard checks on CGPA, branch and years of experience — and \"uncertain\" when the posting doesn't say." },
  { icon: ScanSearch, title: "Real skill gaps", text: "Semantic matching against your actual resume, corroborated by your public GitHub repos." },
  { icon: Wand2, title: "Tailoring with a guardrail", text: "A code-level check rejects any tailored resume that claims a skill you don't have." },
  { icon: BookOpenCheck, title: "Prep plans that fit", text: "Missing skills become an ordered checklist with hours estimated against the deadline." },
  { icon: MousePointerClick, title: "Apply in one click", text: "Email applications sent from your Gmail, or the posting opened with your PDF ready." },
];

const FAQ = [
  {
    q: "Does Pathlight ever apply without me?",
    a: "No. Every application waits on a review screen showing the exact resume and cover note. Email applications need a second confirmation that names the recipient.",
  },
  {
    q: "Will it make my resume sound better than I am?",
    a: "It rewords and reorders what's already on your resume. If a role asks for a skill you don't have, you get a warning — the skill is never added. This is enforced in code, not just requested of the AI.",
  },
  {
    q: "What does it read in my Gmail?",
    a: "Only emails from LinkedIn and Naukri job-alert senders. Send permission is used only when you approve an application. Tokens are encrypted at rest and you can disconnect anytime.",
  },
  {
    q: "Is it free?",
    a: "Yes, for students. Gmail automation is currently available to a limited group while the app is in testing — everything else is open to everyone.",
  },
];

function ProductWindow() {
  return (
    <div className="card overflow-hidden rounded-2xl shadow-card-lg">
      <div className="flex items-center gap-1.5 border-b border-line bg-surface-2 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <div className="mx-auto flex h-6 w-64 items-center justify-center rounded-md border border-line bg-surface text-[11px] text-subtle">
          pathlight.app/applications/aptora
        </div>
      </div>
      <div className="grid md:grid-cols-[190px_1fr]">
        <div className="hidden border-r border-line bg-bg-subtle p-3 md:block">
          <div className="mb-4 flex items-center gap-2 px-1.5">
            <BrandMark size={20} />
            <span className="text-[13px] font-semibold text-fg">Pathlight</span>
          </div>
          {["Dashboard", "Opportunities", "Applications", "Integrations", "Profile"].map((l) => (
            <div
              key={l}
              className={`mb-0.5 flex h-7 items-center justify-between rounded-md px-2 text-[12px] ${
                l === "Applications" ? "bg-surface font-medium text-fg shadow-xs ring-1 ring-line" : "text-muted"
              }`}
            >
              {l}
              {l === "Applications" && <span className="rounded-full bg-accent px-1.5 text-[9px] font-semibold text-white">2</span>}
            </div>
          ))}
        </div>
        <div className="p-5 text-left sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <CompanyAvatar name="Aptora Labs" />
              <div>
                <div className="text-[15px] font-semibold text-fg">Spring Boot Developer</div>
                <div className="text-[13px] text-muted">Aptora Labs · Hyderabad</div>
              </div>
            </div>
            <div className="flex gap-1.5">
              <Badge tone="ok" dot>Eligible</Badge>
              <Badge tone="neutral" icon={Inbox}>From Gmail</Badge>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-[1.3fr_1fr]">
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="mb-2 flex items-center justify-between text-[11px] text-subtle">
                <span className="flex items-center gap-1.5"><FileText size={12} /> Tailored resume</span>
                <span>3 changes</span>
              </div>
              <div className="space-y-1 font-mono text-[11px] leading-relaxed">
                <div className="text-muted">  Java, Spring Boot, REST APIs, SQL</div>
                <div className="rounded bg-bad-soft px-1.5 text-bad line-through decoration-bad/40">− Built REST endpoints for order tracking</div>
                <div className="rounded bg-ok-soft px-1.5 text-ok">+ Built Spring Boot REST APIs for order tracking</div>
                <div className="text-muted">  Campus Events — used by 600 students</div>
              </div>
            </div>
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="mb-2 flex items-center gap-1.5 text-[11px] text-subtle">
                <Mail size={12} /> Cover note
              </div>
              <p className="text-[12px] leading-relaxed text-muted">
                Dear Hiring Team, I&apos;d like to apply for the Spring Boot Developer role. At LocalKart I built Spring
                Boot REST APIs for order tracking…
              </p>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-2 rounded-lg bg-warn-soft px-3 py-2 text-[12px] text-warn">
            <TriangleAlert size={13} className="shrink-0" /> Posting asks for Kubernetes — not on your resume, so it wasn&apos;t added.
          </div>

          <div className="mt-5 flex items-center justify-between gap-3 border-t border-line pt-4">
            <span className="hidden items-center gap-1.5 text-[12px] text-ok sm:flex">
              <ShieldCheck size={13} /> No invented skills
            </span>
            <div className="ml-auto flex gap-2">
              <span className={buttonClasses("ghost", "sm", "pointer-events-none")}>Skip</span>
              <span className={buttonClasses("primary", "sm", "pointer-events-none")}>
                <ExternalLink size={12} /> Apply on LinkedIn
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { user } = useAuth();
  const cta = user ? { href: "/dashboard", label: "Open your dashboard" } : { href: "/register", label: "Get started — it's free" };

  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <Brand />
          <nav className="hidden items-center gap-7 text-[13px] text-muted md:flex">
            <a href="#how" className="transition-colors hover:text-fg">How it works</a>
            <a href="#features" className="transition-colors hover:text-fg">Features</a>
            <a href="#faq" className="transition-colors hover:text-fg">FAQ</a>
          </nav>
          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            {!user && (
              <Link href="/login" className={buttonClasses("ghost", "md", "hidden sm:inline-flex")}>
                Log in
              </Link>
            )}
            <Link href={cta.href} className={buttonClasses("primary", "md")}>
              {user ? "Dashboard" : "Get started"}
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="dot-field pointer-events-none absolute inset-0 opacity-70" aria-hidden />
        <div className="relative mx-auto max-w-4xl px-5 pb-16 pt-20 text-center sm:pt-28">
          <div className="stagger">
            <div className="flex justify-center">
              <Link
                href={cta.href}
                className="inline-flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1.5 pr-3 text-[13px] text-muted shadow-xs transition-colors hover:border-line-strong"
              >
                <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-fg">New</span>
                Built for campus placements
                <ArrowRight size={13} />
              </Link>
            </div>
            <h1 className="mt-8 text-[2.7rem] font-semibold leading-[1.02] tracking-[-0.045em] text-fg sm:text-[4.6rem]">
              Your placement season,
              <br />
              <span className="font-display text-[1.12em] font-normal italic tracking-[-0.02em]">on autopilot.</span>
            </h1>
            <p className="mx-auto mt-7 max-w-xl text-base leading-relaxed text-muted sm:text-[1.07rem]">
              Pathlight reads your job alerts, checks your eligibility, finds your skill gaps and tailors your resume for
              every role — then applies only when you say so.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-2.5 sm:flex-row">
              <Link href={cta.href} className={buttonClasses("primary", "lg", "w-full px-5 sm:w-auto")}>
                {cta.label} <ArrowRight size={15} />
              </Link>
              <a href="#how" className={buttonClasses("secondary", "lg", "w-full px-5 sm:w-auto")}>
                See how it works
              </a>
            </div>
            <div className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[13px] text-subtle">
              {["Never invents skills", "You approve every application", "Encrypted Gmail access"].map((t) => (
                <span key={t} className="inline-flex items-center gap-1.5">
                  <Check size={13} className="text-ok" strokeWidth={2.5} /> {t}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="animate-fade-up relative mx-auto max-w-5xl px-5 pb-24" style={{ animationDelay: "0.2s" }}>
          <ProductWindow />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-16 border-t border-line bg-bg-subtle">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <div className="max-w-2xl">
            <div className="text-[13px] font-medium text-subtle">How it works</div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-[2.6rem] sm:leading-[1.1]">
              From job alert to application, <span className="font-display font-normal italic">in five steps.</span>
            </h2>
          </div>
          <ol className="mt-14 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <li key={step.title} className="bg-surface p-6">
                  <div className="flex items-center justify-between">
                    <Icon size={18} className="text-fg" strokeWidth={1.8} />
                    <span className="font-mono text-[11px] text-subtle">0{i + 1}</span>
                  </div>
                  <div className="mt-8 text-[15px] font-semibold text-fg">{step.title}</div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{step.text}</p>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-16 border-t border-line">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
            <div>
              <div className="text-[13px] font-medium text-subtle">Features</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-[2.6rem] sm:leading-[1.1]">
                Everything placement season needs.
              </h2>
              <p className="mt-4 max-w-sm leading-relaxed text-muted">
                Five specialised agents, each doing one job well — and showing its work every time.
              </p>
            </div>
            <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <div key={title} className="bg-surface p-6 transition-colors hover:bg-surface-2">
                  <Icon size={18} className="text-fg" strokeWidth={1.8} />
                  <h3 className="mt-5 text-[15px] font-semibold text-fg">{title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Honesty */}
      <section className="border-t border-line bg-bg-subtle">
        <div className="mx-auto max-w-4xl px-5 py-24 text-center">
          <Sparkles size={20} className="mx-auto text-subtle" strokeWidth={1.6} />
          <p className="mt-6 font-display text-[2rem] leading-[1.2] tracking-[-0.01em] text-fg sm:text-[2.9rem]">
            “An assistant that handles the busywork of placement season — and never embellishes who you are.”
          </p>
          <div className="mx-auto mt-12 grid max-w-3xl gap-6 text-left sm:grid-cols-3">
            {[
              { icon: ShieldCheck, t: "Never fabricates", d: "Claimed skills are checked against your original resume." },
              { icon: MousePointerClick, t: "You stay in control", d: "Every application waits for your approval." },
              { icon: Lock, t: "Private by default", d: "Encrypted tokens. Alerts only. Revoke anytime." },
            ].map(({ icon: Icon, t, d }) => (
              <div key={t}>
                <Icon size={17} className="text-fg" strokeWidth={1.8} />
                <div className="mt-3 text-sm font-semibold text-fg">{t}</div>
                <p className="mt-1 text-[13px] leading-relaxed text-muted">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-16 border-t border-line">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-24 lg:grid-cols-[1fr_2fr]">
          <div>
            <div className="text-[13px] font-medium text-subtle">FAQ</div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-[2.6rem] sm:leading-[1.1]">
              Questions, answered.
            </h2>
          </div>
          <div className="divide-y divide-line border-y border-line">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group py-1">
                <summary className="flex cursor-pointer items-center justify-between gap-4 py-4 text-[15px] font-medium text-fg">
                  {q}
                  <ChevronDown size={16} className="shrink-0 text-subtle transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <p className="pb-5 pr-8 text-sm leading-relaxed text-muted">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-line">
        <div className="mx-auto max-w-3xl px-5 py-28 text-center">
          <h2 className="text-4xl font-semibold tracking-[-0.04em] text-fg sm:text-6xl">
            Stop refreshing job boards.
            <br />
            <span className="font-display font-normal italic">Start getting shortlisted.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-md text-muted">
            Two minutes to set up: add your CGPA, upload your resume, connect Gmail. Pathlight takes it from there.
          </p>
          <Link href={cta.href} className={buttonClasses("primary", "lg", "mt-9 px-5")}>
            {cta.label} <ArrowRight size={15} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 text-[13px] text-subtle sm:flex-row">
          <Brand />
          <p>Made for students, by a student. Your data is never sold or shared.</p>
        </div>
      </footer>
    </div>
  );
}
