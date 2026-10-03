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
import { Reveal, ScoreRing, WordRise } from "@/components/Motion";

// Public landing page — what a friend sees when you share the link. Signed-in users
// see the same page with "Open dashboard" in place of the sign-up calls to action.

const STEPS = [
  { icon: Inbox, title: "Discover", text: "Searches 25+ company career pages and job boards daily, plus your LinkedIn & Naukri alerts." },
  { icon: BadgeCheck, title: "Check eligibility", text: "CGPA, branch and experience checked with evidence. Unclear? It says so." },
  { icon: ScanSearch, title: "Find skill gaps", text: "Your resume and GitHub against the role: matched, weak, missing." },
  { icon: Wand2, title: "Tailor", text: "An ATS-ready resume and cover note — reworded, never invented, links intact." },
  { icon: MousePointerClick, title: "You approve", text: "Nothing goes out until you say so. Then it's one click." },
];

const FEATURES = [
  { icon: Inbox, title: "Opportunities find you", text: "Fresh roles from company career pages and job boards every day, ranked for your skills, level and cities — plus every Gmail job alert." },
  { icon: BadgeCheck, title: "Honest eligibility", text: "Hard checks on CGPA, branch and years of experience — and \"uncertain\" when the posting doesn't say." },
  { icon: ScanSearch, title: "Real skill gaps", text: "Semantic matching against your actual resume, corroborated by your public GitHub repos." },
  { icon: Wand2, title: "ATS-ready, honestly", text: "Every tailored resume is scored like an ATS would and revised until it hits the best score you can honestly get." },
  { icon: BookOpenCheck, title: "Prep plans that fit", text: "Missing skills become an ordered checklist with hours estimated against the deadline." },
  { icon: MousePointerClick, title: "Apply in one click", text: "Email applications sent from your Gmail, or the posting opened with your PDF ready." },
];

const SOURCES = [
  "Groww", "Meesho", "CRED", "Paytm", "Databricks", "MongoDB", "Stripe", "HackerRank", "Druva", "InMobi",
  "Okta", "Zscaler", "GitLab", "Rubrik", "Twilio", "Coinbase", "Remotive", "Himalayas", "LinkedIn alerts", "Naukri alerts",
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
    q: "Will my resume score 100 on an ATS?",
    a: "If you have every skill the job asks for, yes — Pathlight mirrors the posting's wording, fixes structure and keeps your links clickable, then re-checks until nothing honest is left to gain. If the job wants something you don't have, it tells you exactly which skills cost those points instead of faking them.",
  },
  {
    q: "Where do the jobs come from?",
    a: "Public job boards of companies like Groww, Meesho, CRED, Paytm, Databricks and MongoDB, remote boards like Remotive and Himalayas, and your own LinkedIn and Naukri alert emails if you connect Gmail. Each links to the original posting.",
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
    <div className="hero-window card overflow-hidden rounded-2xl shadow-card-lg">
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
          {["Dashboard", "Jobs for you", "Applications", "Gmail alerts", "Profile"].map((l) => (
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
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <Badge tone="ok" dot>Eligible</Badge>
                <Badge tone="neutral" icon={Inbox}>From Gmail</Badge>
              </div>
              <ScoreRing value={96} size={46} stroke={4} tone="ok" />
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-[1.3fr_1fr]">
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="mb-2 flex items-center justify-between text-[11px] text-subtle">
                <span className="flex items-center gap-1.5"><FileText size={12} /> Tailored resume</span>
                <span>3 changes</span>
              </div>
              <Reveal sequence className="space-y-1 font-mono text-[11px] leading-relaxed">
                <div className="text-muted">  Java, Spring Boot, REST APIs, SQL</div>
                <div className="rounded bg-bad-soft px-1.5 text-bad line-through decoration-bad/40">− Built REST endpoints for order tracking</div>
                <div className="rounded bg-ok-soft px-1.5 text-ok">+ Built Spring Boot REST APIs for order tracking</div>
                <div className="text-muted">  Campus Events — used by 600 students</div>
              </Reveal>
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
          <div>
            <div className="animate-fade-in flex justify-center">
              <Link
                href={cta.href}
                className="inline-flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1.5 pr-3 text-[13px] text-muted shadow-xs transition-colors hover:border-line-strong"
              >
                <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-fg">New</span>
                Jobs from 25+ company career pages, daily
                <ArrowRight size={13} />
              </Link>
            </div>
            <h1 className="mt-8 text-[2.7rem] font-semibold leading-[1.04] tracking-[-0.045em] text-fg sm:text-[4.6rem]">
              <WordRise text="Your placement season," />
              <br />
              <WordRise text="on autopilot." start={3} className="font-display text-[1.12em] font-normal italic tracking-[-0.02em]" />
            </h1>
            <p className="animate-fade-up mx-auto mt-7 max-w-xl text-base leading-relaxed text-muted sm:text-[1.07rem]" style={{ animationDelay: "0.45s" }}>
              Pathlight finds jobs that fit you, checks your eligibility, and tailors an ATS-ready resume for every role
              — without inventing a single skill. It applies only when you say so.
            </p>
            <div className="animate-fade-up mt-9 flex flex-col items-center justify-center gap-2.5 sm:flex-row" style={{ animationDelay: "0.55s" }}>
              <Link href={cta.href} className={buttonClasses("primary", "lg", "w-full px-5 sm:w-auto")}>
                {cta.label} <ArrowRight size={15} />
              </Link>
              <a href="#how" className={buttonClasses("secondary", "lg", "w-full px-5 sm:w-auto")}>
                See how it works
              </a>
            </div>
            <div className="animate-fade-up mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[13px] text-subtle" style={{ animationDelay: "0.65s" }}>
              {["Never invents skills", "ATS-scored resumes", "You approve every application"].map((t) => (
                <span key={t} className="inline-flex items-center gap-1.5">
                  <Check size={13} className="text-ok" strokeWidth={2.5} /> {t}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="relative mx-auto max-w-5xl px-5 pb-16 [perspective:1600px]">
          <ProductWindow />
        </div>
        <div className="relative mx-auto max-w-5xl px-5 pb-20">
          <p className="text-center text-[12px] font-medium uppercase tracking-[0.14em] text-subtle">Jobs straight from the source</p>
          <div className="marquee mt-5 overflow-hidden">
            <div className="marquee-track flex w-max gap-12 pr-12">
              {[...SOURCES, ...SOURCES].map((name, i) => (
                <span key={i} className="whitespace-nowrap text-[17px] font-semibold tracking-[-0.02em] text-subtle/90">
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-16 border-t border-line bg-bg-subtle">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <Reveal className="max-w-2xl">
            <div className="text-[13px] font-medium text-subtle">How it works</div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-[2.6rem] sm:leading-[1.1]">
              From job post to application, <span className="font-display font-normal italic">in five steps.</span>
            </h2>
          </Reveal>
          <ol className="mt-14 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <Reveal as="li" key={step.title} delay={i * 90} className="bg-surface p-6">
                  <div className="flex items-center justify-between">
                    <Icon size={18} className="text-fg" strokeWidth={1.8} />
                    <span className="font-mono text-[11px] text-subtle">0{i + 1}</span>
                  </div>
                  <div className="mt-8 text-[15px] font-semibold text-fg">{step.title}</div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{step.text}</p>
                </Reveal>
              );
            })}
          </ol>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-16 border-t border-line">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
            <Reveal>
              <div className="text-[13px] font-medium text-subtle">Features</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-[2.6rem] sm:leading-[1.1]">
                Everything placement season needs.
              </h2>
              <p className="mt-4 max-w-sm leading-relaxed text-muted">
                Specialised agents, each doing one job well — and showing its work every time.
              </p>
            </Reveal>
            <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
              {FEATURES.map(({ icon: Icon, title, text }, i) => (
                <Reveal key={title} delay={(i % 2) * 80 + Math.floor(i / 2) * 60} className="group bg-surface p-6 transition-colors duration-300 hover:bg-surface-2">
                  <Icon size={18} className="text-fg transition-transform duration-500 group-hover:-translate-y-0.5" strokeWidth={1.8} />
                  <h3 className="mt-5 text-[15px] font-semibold text-fg">{title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{text}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Honesty */}
      <section className="border-t border-line bg-bg-subtle">
        <div className="mx-auto max-w-4xl px-5 py-24 text-center">
          <Sparkles size={20} className="mx-auto text-subtle" strokeWidth={1.6} />
          <Reveal as="p" className="mt-6 font-display text-[2rem] leading-[1.2] tracking-[-0.01em] text-fg sm:text-[2.9rem]">
            “An assistant that handles the busywork of placement season — and never embellishes who you are.”
          </Reveal>
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
          <Reveal as="h2" className="text-4xl font-semibold tracking-[-0.04em] text-fg sm:text-6xl">
            Stop refreshing job boards.
            <br />
            <span className="font-display font-normal italic">Start getting shortlisted.</span>
          </Reveal>
          <p className="mx-auto mt-6 max-w-md text-muted">
            Two minutes to set up: tell Pathlight what you&apos;re looking for and upload your resume. It takes it from there.
          </p>
          <Link href={cta.href} className={buttonClasses("primary", "lg", "mt-9 px-5")}>
            {cta.label} <ArrowRight size={15} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 text-[13px] text-subtle sm:flex-row">
          <Brand />
          <div className="flex flex-col items-center gap-2 sm:items-end">
            <p>Made for students, by a student. Your data is never sold.</p>
            <div className="flex gap-4">
              <Link href="/privacy" className="hover:text-fg">Privacy</Link>
              <Link href="/terms" className="hover:text-fg">Terms</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
