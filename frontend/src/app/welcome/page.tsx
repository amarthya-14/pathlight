"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, FileText, Link2, Loader2, Mail, UploadCloud } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { firstName, markOnboardingSeen, useRequireAuth } from "@/lib/auth-context";
import { profilePayload } from "@/lib/profile";
import { BrandMark } from "@/components/Brand";
import { FullScreenLoader } from "@/components/Shell";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Chip, ChipPicker } from "@/components/Chips";
import { Alert, Button, buttonClasses, cx, Field, TextInput } from "@/components/ui";

// First-run flow: who you are, what you study, what you're looking for, your resume.
// Every answer feeds something concrete — the greeting, eligibility checks, the job feed
// ranking, tailoring — and each step says what it's used for.

const ROLE_SUGGESTIONS = [
  "Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer", "Data Analyst",
  "Data Scientist", "ML Engineer", "AI Engineer", "DevOps Engineer", "Cloud Engineer", "QA Engineer",
  "Mobile Developer", "Security Engineer", "Product Analyst",
];
const CITY_SUGGESTIONS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi NCR", "Kolkata", "Ahmedabad"];
const BRANCHES = ["CSE", "IT", "AI & ML", "AI & DS", "ECE", "EEE", "EIE", "ME", "CE", "Chemical", "Biotech"];
const YEAR_NOW = new Date().getFullYear();
const GRAD_YEARS = Array.from({ length: 7 }, (_, i) => YEAR_NOW - 1 + i);
const EXPERIENCE = [
  { value: "0", label: "Fresher" },
  { value: "0.5", label: "< 1 year" },
  { value: "1", label: "1 year" },
  { value: "2", label: "2 years" },
  { value: "3", label: "3+ years" },
];

const STEPS = ["You", "Studies", "Goals", "Resume", "Done"] as const;

export default function WelcomePage() {
  const { user, profile, loading, setUser, setProfile } = useRequireAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [college, setCollege] = useState("");
  const [gradYear, setGradYear] = useState("");
  const [branch, setBranch] = useState("");
  const [cgpa, setCgpa] = useState("");
  const [experience, setExperience] = useState("0");
  const [roles, setRoles] = useState<string[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [remote, setRemote] = useState(true);
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [linksFound, setLinksFound] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const seeded = useRef(false);

  // Seed the form once from what Pathlight already knows.
  useEffect(() => {
    if (!user || seeded.current) return;
    seeded.current = true;
    setName(user.full_name ?? "");
    if (profile) {
      setCollege(profile.college ?? "");
      setGradYear(profile.graduation_year?.toString() ?? "");
      setBranch(profile.branch ?? "");
      setCgpa(profile.cgpa?.toString() ?? "");
      setExperience(profile.experience_years?.toString() ?? "0");
      setRoles(profile.target_roles ?? []);
      setCities(profile.preferred_locations ?? []);
      setRemote(profile.open_to_remote ?? true);
    }
    api
      .listDocuments()
      .then((docs) => {
        const resume = docs.find((d) => d.doc_type === "resume");
        if (resume) setResumeName(resume.original_filename);
      })
      .catch(() => {});
  }, [user, profile]);

  if (loading || !user) return <FullScreenLoader />;

  const go = (next: number) => {
    setDirection(next > step ? 1 : -1);
    setError(null);
    setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const save = async (fn: () => Promise<void>, next: number) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      go(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save that — please try again.");
    } finally {
      setBusy(false);
    }
  };

  const saveName = () =>
    save(async () => {
      setUser(await api.updateMe(name.trim()));
    }, 1);

  const saveStudies = () =>
    save(async () => {
      setProfile(
        await api.upsertProfile(
          profilePayload(profile, {
            college: college.trim() || null,
            graduation_year: gradYear ? Number(gradYear) : null,
            branch: branch.trim() || null,
            cgpa: cgpa ? Number(cgpa) : null,
            experience_years: Number(experience),
          })
        )
      );
    }, 2);

  const saveGoals = () =>
    save(async () => {
      setProfile(
        await api.upsertProfile(
          profilePayload(profile, { target_roles: roles, preferred_locations: cities, open_to_remote: remote })
        )
      );
    }, 3);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const doc = await api.uploadDocument(file, "resume");
      if (!doc.extracted_text?.trim()) {
        setError("We couldn't read text from that file (probably a scanned PDF). Export it as a text PDF and try again.");
        return;
      }
      setResumeName(doc.original_filename);
      const urls = doc.extracted_text.match(/(?:linkedin\.com|github\.com|gitlab\.com)\/[^\s|,;)]+|[\w-]+\.(?:dev|me|io|app|wixstudio\.io)\/?[^\s|,;)]*/gi);
      setLinksFound([...new Set(urls ?? [])].slice(0, 6));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Upload failed — please try again.");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const skip = () => {
    markOnboardingSeen();
    router.push("/dashboard");
  };

  const hello = firstName({ ...user, full_name: name || user.full_name });
  const canSkip = Boolean(user.full_name);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-5 py-4 sm:px-8">
        <span className="brand-animate">
          <BrandMark size={26} animate />
        </span>
        <div className="flex items-center gap-1">
          {canSkip && step < 4 && (
            <button onClick={skip} className="rounded-md px-2.5 py-1.5 text-[13px] text-muted hover:bg-surface-hover hover:text-fg">
              Skip for now
            </button>
          )}
          <ThemeToggle />
        </div>
      </header>

      <div className="mx-auto w-full max-w-xl flex-1 px-5 pb-16 pt-4 sm:pt-10">
        {/* Progress: one segment per step, filling as you go. */}
        <div className="mb-10 flex gap-1.5" aria-label={`Step ${step + 1} of ${STEPS.length}`}>
          {STEPS.map((label, i) => (
            <div key={label} className="flex-1">
              <div className="h-1 overflow-hidden rounded-full bg-surface-hover">
                <div
                  className="h-full rounded-full bg-ink transition-[width] duration-700"
                  style={{ width: i <= step ? "100%" : "0%", transitionTimingFunction: "var(--ease-out)" }}
                />
              </div>
              <div className={cx("mt-2 text-[11px] font-medium transition-colors", i <= step ? "text-fg" : "text-subtle")}>{label}</div>
            </div>
          ))}
        </div>

        <div key={step} className={direction === 1 ? "step-forward" : "step-back"}>
          {step === 0 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim()) saveName();
              }}
            >
              <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-fg">
                Welcome to Pathlight. <span className="font-display font-normal italic text-muted">What should we call you?</span>
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                Your name goes on your tailored resumes and cover notes — use it the way recruiters should see it.
              </p>
              <div className="mt-8">
                <Field label="Full name">
                  <TextInput autoFocus required value={name} onChange={(e) => setName(e.target.value)} placeholder="Asha Rao" className="h-11 text-base" />
                </Field>
              </div>
              {error && <Alert tone="bad" className="mt-4">{error}</Alert>}
              <div className="mt-8 flex justify-end">
                <Button type="submit" size="lg" loading={busy} disabled={!name.trim()}>
                  Continue {!busy && <ArrowRight size={16} />}
                </Button>
              </div>
            </form>
          )}

          {step === 1 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveStudies();
              }}
            >
              <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-fg">
                Nice to meet you, {hello}. <span className="font-display font-normal italic text-muted">Where are you studying?</span>
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                Pathlight checks every posting&apos;s CGPA, branch and batch rules against these — so you only spend time on roles you can actually apply to.
              </p>
              <div className="mt-8 space-y-5">
                <Field label="College">
                  <TextInput value={college} onChange={(e) => setCollege(e.target.value)} placeholder="VIT-AP University" />
                </Field>
                <div className="grid gap-5 sm:grid-cols-2">
                  <Field label="Graduation year">
                    <select
                      value={gradYear}
                      onChange={(e) => setGradYear(e.target.value)}
                      className="h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-fg shadow-xs focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
                    >
                      <option value="">Select…</option>
                      {GRAD_YEARS.map((y) => (
                        <option key={y} value={y}>
                          {y}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="CGPA (out of 10)">
                    <TextInput type="number" step="0.01" min="0" max="10" value={cgpa} onChange={(e) => setCgpa(e.target.value)} placeholder="8.50" />
                  </Field>
                </div>
                <Field label="Branch">
                  <div className="flex flex-wrap gap-2">
                    {BRANCHES.map((b) => (
                      <Chip key={b} selected={branch === b} onClick={() => setBranch(branch === b ? "" : b)}>
                        {b}
                      </Chip>
                    ))}
                  </div>
                </Field>
                <Field label="Full-time work experience" hint="Internships don't count here — postings' “X years” means full-time.">
                  <div className="flex flex-wrap gap-2">
                    {EXPERIENCE.map((o) => (
                      <Chip key={o.value} selected={experience === o.value} onClick={() => setExperience(o.value)}>
                        {o.label}
                      </Chip>
                    ))}
                  </div>
                </Field>
              </div>
              {error && <Alert tone="bad" className="mt-4">{error}</Alert>}
              <div className="mt-8 flex justify-between">
                <Button type="button" variant="ghost" onClick={() => go(0)}>
                  <ArrowLeft size={15} /> Back
                </Button>
                <Button type="submit" size="lg" loading={busy}>
                  Continue {!busy && <ArrowRight size={16} />}
                </Button>
              </div>
            </form>
          )}

          {step === 2 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveGoals();
              }}
            >
              <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-fg">
                What are you <span className="font-display font-normal italic">looking for?</span>
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                Pathlight searches company career pages and job boards every day and ranks what it finds by these.
              </p>
              <div className="mt-8 space-y-7">
                <Field label="Roles you want (pick up to 6)">
                  <ChipPicker options={ROLE_SUGGESTIONS} value={roles} onChange={setRoles} placeholder="Another role…" />
                </Field>
                <Field label="Where you'd like to work">
                  <ChipPicker options={CITY_SUGGESTIONS} value={cities} onChange={setCities} placeholder="Another city…" />
                </Field>
                <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border border-line bg-surface px-4 py-3.5">
                  <span>
                    <span className="block text-[13px] font-medium text-fg">Open to remote roles</span>
                    <span className="block text-xs text-subtle">Includes remote jobs that hire from India.</span>
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={remote}
                    onClick={() => setRemote(!remote)}
                    className={cx("relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300", remote ? "bg-ink" : "bg-line-strong")}
                  >
                    <span
                      className={cx(
                        "absolute left-0 top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-transform duration-300",
                        remote ? "translate-x-[22px]" : "translate-x-0.5"
                      )}
                      style={{ transitionTimingFunction: "var(--ease-out)" }}
                    />
                  </button>
                </label>
              </div>
              {error && <Alert tone="bad" className="mt-4">{error}</Alert>}
              <div className="mt-8 flex justify-between">
                <Button type="button" variant="ghost" onClick={() => go(1)}>
                  <ArrowLeft size={15} /> Back
                </Button>
                <Button type="submit" size="lg" loading={busy}>
                  Continue {!busy && <ArrowRight size={16} />}
                </Button>
              </div>
            </form>
          )}

          {step === 3 && (
            <div>
              <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-fg">
                Last thing: <span className="font-display font-normal italic">your resume.</span>
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                It&apos;s the only source of truth for tailoring. Pathlight rewords and reorders it per job — it never adds a skill you don&apos;t have. Links (GitHub, LinkedIn, projects) are kept and stay clickable.
              </p>

              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) upload(file);
                }}
                className={cx(
                  "mt-8 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-12 text-center transition-[border-color,background-color,transform] duration-300",
                  dragging ? "scale-[1.01] border-ink bg-surface-hover" : "border-line-strong hover:border-subtle hover:bg-surface-2"
                )}
              >
                <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface shadow-xs">
                  {busy ? <Loader2 size={18} className="animate-spin text-muted" /> : resumeName ? <FileText size={18} className="text-ok" /> : <UploadCloud size={18} className="text-muted" />}
                </span>
                <span className="text-sm font-medium text-fg">
                  {busy ? "Reading your resume…" : resumeName ? resumeName : "Drop your resume PDF here"}
                </span>
                <span className="mt-1 text-xs text-subtle">
                  {resumeName ? "Drop another file to replace it" : "or click to browse · text-based PDF or TXT · up to 10MB"}
                </span>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  className="sr-only"
                  disabled={busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) upload(file);
                  }}
                />
              </label>

              {linksFound.length > 0 && (
                <div className="animate-fade-in mt-4 rounded-xl border border-line bg-surface px-4 py-3">
                  <div className="flex items-center gap-2 text-[13px] font-medium text-fg">
                    <Link2 size={14} className="text-ok" /> Found {linksFound.length} link{linksFound.length === 1 ? "" : "s"} — they&apos;ll stay clickable on every tailored resume
                  </div>
                  <ul className="mt-2 space-y-1">
                    {linksFound.map((l) => (
                      <li key={l} className="truncate font-mono text-[12px] text-muted">
                        {l}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {error && <Alert tone="bad" className="mt-4">{error}</Alert>}

              <div className="mt-8 flex justify-between">
                <Button type="button" variant="ghost" onClick={() => go(2)}>
                  <ArrowLeft size={15} /> Back
                </Button>
                <Button
                  size="lg"
                  onClick={() => {
                    markOnboardingSeen();
                    go(4);
                  }}
                  disabled={busy} variant={resumeName ? "primary" : "secondary"}>
                  {resumeName ? "Continue" : "I'll add it later"} <ArrowRight size={16} />
                </Button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-ink text-ink-fg">
                <span className="brand-animate">
                  <Check size={26} strokeWidth={2.4} />
                </span>
              </div>
              <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.03em] text-fg">
                You&apos;re all set, {hello}.
              </h1>
              <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-muted">
                {roles.length
                  ? `Pathlight is lining up ${roles.slice(0, 2).join(" and ")} roles${cities.length ? ` in ${cities.slice(0, 2).join(" and ")}` : ""}${remote ? " and remote" : ""}. Track one and it'll check eligibility, find skill gaps and tailor your resume.`
                  : "Track any job and Pathlight will check eligibility, find skill gaps and tailor your resume for it."}
              </p>
              <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                <Link href="/jobs" className={buttonClasses("primary", "lg")}>
                  See jobs picked for you <ArrowRight size={16} />
                </Link>
                <Link href="/integrations" className={buttonClasses("secondary", "lg")}>
                  <Mail size={15} /> Also read my job alerts
                </Link>
              </div>
              <button onClick={() => router.push("/dashboard")} className="mt-6 text-[13px] text-muted underline-offset-4 hover:text-fg hover:underline">
                Go to dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
