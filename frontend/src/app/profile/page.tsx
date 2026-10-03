"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Code2, Download, FileText, Link2, Loader2, Sparkles, Trash2, UploadCloud } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError, saveBlob } from "@/lib/api";
import type { DocumentOut, ProfileOut } from "@/lib/types";
import { profilePayload } from "@/lib/profile";
import { AiKeysCard } from "@/components/AiKeysCard";
import { ChipPicker } from "@/components/Chips";
import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Field, PageHeader, PageSkeleton, Progress, TextArea, TextInput } from "@/components/ui";

const BRANCHES = ["CSE", "IT", "AI & DS", "AI & ML", "ECE", "EEE", "EIE", "ME", "CE", "Chemical", "Biotech"];
const EXPERIENCE = [
  { value: "0", label: "Fresher (no full-time experience)" },
  { value: "0.5", label: "Less than 1 year" },
  { value: "1", label: "1 year" },
  { value: "2", label: "2 years" },
  { value: "3", label: "3 years" },
  { value: "5", label: "5+ years" },
];

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-4 border-t border-line py-8 first:border-t-0 first:pt-0 md:grid-cols-[260px_1fr] md:gap-10">
      <div>
        <h2 className="text-[15px] font-semibold text-fg">{title}</h2>
        <p className="mt-1 text-[13px] leading-relaxed text-muted">{description}</p>
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

const ROLE_SUGGESTIONS = ["Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer", "Data Analyst", "ML Engineer", "AI Engineer", "DevOps Engineer"];
const CITY_SUGGESTIONS = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi NCR"];

export default function ProfilePage() {
  const { user, loading: authLoading, setUser, setProfile: setContextProfile } = useRequireAuth();
  const [name, setName] = useState("");
  const [college, setCollege] = useState("");
  const [gradYear, setGradYear] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [remote, setRemote] = useState(true);
  const [linkCount, setLinkCount] = useState<number | null>(null);
  const [expectedCtc, setExpectedCtc] = useState("");
  const [noticePeriod, setNoticePeriod] = useState("");
  const toast = useToast();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [cgpa, setCgpa] = useState("");
  const [branch, setBranch] = useState("");
  const [experience, setExperience] = useState("0");
  const [githubUsername, setGithubUsername] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [showPaste, setShowPaste] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadDocuments = () => {
    api.listDocuments().then(setDocuments).catch(() => {});
  };

  useEffect(() => {
    if (!user) return;
    setName(user.full_name ?? "");
    api.getProfile().then((p) => {
      setProfile(p);
      setCollege(p.college ?? "");
      setGradYear(p.graduation_year?.toString() ?? "");
      setRoles(p.target_roles ?? []);
      setCities(p.preferred_locations ?? []);
      setRemote(p.open_to_remote ?? true);
      setExpectedCtc(p.expected_ctc_lpa?.toString() ?? "");
      setNoticePeriod(p.notice_period ?? "");
      setCgpa(p.cgpa?.toString() ?? "");
      setBranch(p.branch ?? "");
      setExperience(p.experience_years?.toString() ?? "0");
      setGithubUsername(p.github_username ?? "");
    });
    loadDocuments();
  }, [user]);

  const onSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (name.trim() && name.trim() !== user?.full_name) setUser(await api.updateMe(name.trim()));
      const saved = await api.upsertProfile(
        profilePayload(profile, {
          cgpa: cgpa ? Number(cgpa) : null,
          branch: branch || null,
          github_username: githubUsername || null,
          experience_years: Number(experience),
          college: college.trim() || null,
          graduation_year: gradYear ? Number(gradYear) : null,
          target_roles: roles,
          preferred_locations: cities,
          open_to_remote: remote,
          expected_ctc_lpa: expectedCtc ? Number(expectedCtc) : null,
          notice_period: noticePeriod.trim() || null,
        })
      );
      setProfile(saved);
      setContextProfile(saved);
      toast("Profile saved", { description: "Job matches update right away. Use “Re-check” on an application to re-run eligibility." });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  // Uploads as soon as a file is chosen or dropped — no second "submit" click.
  const uploadFile = async (file: File) => {
    setUploading(true);
    setResumeError(null);
    try {
      const doc = await api.uploadDocument(file, "resume");
      loadDocuments();
      setLinkCount((doc.extracted_text?.match(/(?:github|linkedin|gitlab)\.com\/\S+/gi) ?? []).length);
      if (!doc.extracted_text || !doc.extracted_text.trim()) {
        setResumeError(
          "Uploaded, but no text could be read from this file (likely a scanned or image PDF). Export your resume as a text-based PDF, or paste the text instead."
        );
      } else {
        toast("Resume uploaded", { description: "Open any application and generate a tailored resume." });
      }
    } catch (err) {
      setResumeError(err instanceof ApiError ? err.detail : "Failed to upload resume");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onPasteResume = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    setResumeError(null);
    try {
      await api.pasteDocument({ doc_type: "resume", title: "Resume", text: resumeText });
      setResumeText("");
      setShowPaste(false);
      loadDocuments();
      toast("Resume saved");
    } catch (err) {
      setResumeError(err instanceof ApiError ? err.detail : "Failed to save resume");
    } finally {
      setUploading(false);
    }
  };

  if (authLoading || !user) return null;
  if (!profile) return <PageSkeleton />;

  const latestResume = documents.find((d) => d.doc_type === "resume"); // list is newest-first
  const completeness = [
    Boolean(user.full_name),
    Boolean(profile.cgpa && profile.branch),
    Boolean(profile.graduation_year),
    profile.target_roles.length > 0,
    Boolean(latestResume),
  ].filter(Boolean).length;

  return (
    <div className="max-w-4xl">
      <div className="animate-fade-in">
        <PageHeader
          title="Profile"
          subtitle="Your details power eligibility checks, skill gaps and tailored resumes."
          actions={
            <div className="flex items-center gap-3 text-[13px] text-muted">
              <Progress value={completeness * 20} tone="ok" className="w-24" />
              {completeness * 20}% complete
            </div>
          }
        />
      </div>

      <Card className="p-5 sm:p-7">
        <form onSubmit={onSaveProfile}>
        <Section title="About you" description="Your name goes on tailored resumes and cover notes.">
          <div className="space-y-4">
            <Field label="Full name">
              <TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Asha Rao" required />
            </Field>
            <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
              <Field label="College">
                <TextInput value={college} onChange={(e) => setCollege(e.target.value)} placeholder="VIT-AP University" />
              </Field>
              <Field label="Graduation year">
                <TextInput type="number" min="1990" max="2040" value={gradYear} onChange={(e) => setGradYear(e.target.value)} placeholder="2027" />
              </Field>
            </div>
          </div>
        </Section>

        <Section title="What you're looking for" description="Ranks the jobs Pathlight finds for you every day.">
          <div className="space-y-5">
            <Field label="Target roles">
              <ChipPicker options={ROLE_SUGGESTIONS} value={roles} onChange={setRoles} placeholder="Another role…" />
            </Field>
            <Field label="Preferred locations">
              <ChipPicker options={CITY_SUGGESTIONS} value={cities} onChange={setCities} placeholder="Another city…" />
            </Field>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] text-fg">
              <input type="checkbox" className="h-3.5 w-3.5 accent-[var(--ink)]" checked={remote} onChange={(e) => setRemote(e.target.checked)} />
              Open to remote roles that hire from India
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Expected CTC (LPA)" hint="Used for application forms that ask. Leave blank for “as per company standards”.">
                <TextInput type="number" min="0" step="0.5" value={expectedCtc} onChange={(e) => setExpectedCtc(e.target.value)} placeholder="6" />
              </Field>
              <Field label="When can you join?" hint="Default: from June of your graduation year.">
                <TextInput value={noticePeriod} onChange={(e) => setNoticePeriod(e.target.value)} placeholder="Immediate" />
              </Field>
            </div>
          </div>
        </Section>

        <Section title="Academic details" description="Checked against each posting's CGPA, branch and experience requirements.">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="CGPA">
                <TextInput type="number" step="0.01" min="0" max="10" placeholder="8.50" value={cgpa} onChange={(e) => setCgpa(e.target.value)} />
              </Field>
              <Field label="Branch">
                <TextInput type="text" list="branches" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="CSE" />
                <datalist id="branches">
                  {BRANCHES.map((b) => (
                    <option key={b} value={b} />
                  ))}
                </datalist>
              </Field>
            </div>
            <Field label="Work experience" hint="Full-time experience only — internships don't count toward a posting's “X years” requirement.">
              <select
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                className="h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-fg shadow-xs focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
              >
                {EXPERIENCE.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="GitHub username" hint="Optional. Adds supporting evidence from your public repos to Skill Gap — it never changes the verdict itself.">
              <div className="relative">
                <Code2 size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
                <TextInput type="text" value={githubUsername} onChange={(e) => setGithubUsername(e.target.value)} placeholder="octocat" className="pl-8" />
              </div>
            </Field>
            {error && <Alert tone="bad">{error}</Alert>}
            <div className="flex justify-end">
              <Button type="submit" loading={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </div>
        </Section>
        </form>

        <Section title="Resume" description="The single source of truth for tailoring. Pathlight rewords it per role, but never adds to it.">
          {latestResume ? (
            <div className="mb-3 flex items-center gap-3 rounded-lg border border-line bg-surface-2 px-3.5 py-3">
              <FileText size={16} className="shrink-0 text-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-fg">{latestResume.original_filename}</div>
                <div className="text-xs text-subtle">
                  Uploaded {new Date(latestResume.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
                </div>
              </div>
              <CheckCircle2 size={16} className="shrink-0 text-ok" />
            </div>
          ) : (
            <Alert tone="warn" className="mb-3">
              No resume yet — skill gaps will show everything as missing, and tailoring is disabled.
            </Alert>
          )}

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
              if (file) uploadFile(file);
            }}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-5 py-8 text-center transition-colors ${
              dragging ? "border-accent bg-accent-soft" : "border-line-strong hover:border-subtle hover:bg-surface-2"
            }`}
          >
            <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface shadow-xs">
              {uploading ? <Loader2 size={16} className="animate-spin text-muted" /> : <UploadCloud size={16} className="text-muted" />}
            </span>
            <span className="text-[13px] font-medium text-fg">
              {uploading ? "Uploading and indexing…" : latestResume ? "Drop a new resume to replace it" : "Drop your resume here"}
            </span>
            <span className="mt-1 text-xs text-subtle">
              or <span className="font-medium text-fg underline underline-offset-2">browse</span> · PDF or TXT up to 10MB · text-based PDFs only
            </span>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              className="sr-only"
              data-testid="resume-file-input"
              disabled={uploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadFile(file);
              }}
            />
          </label>

          {linkCount !== null && linkCount > 0 && (
            <p className="animate-fade-in mt-3 flex items-center gap-1.5 text-xs text-ok">
              <Link2 size={13} /> Kept {linkCount} profile/project link{linkCount === 1 ? "" : "s"} — they stay clickable on tailored resumes.
            </p>
          )}

          {resumeError && (
            <Alert tone="bad" className="mt-3">
              {resumeError}
            </Alert>
          )}

          <button type="button" onClick={() => setShowPaste((v) => !v)} className="mt-3 text-xs text-muted underline-offset-4 hover:text-fg hover:underline">
            {showPaste ? "Hide text paste" : "Or paste resume text instead"}
          </button>
          {showPaste && (
            <form onSubmit={onPasteResume} className="animate-fade-in mt-3 space-y-2">
              <TextArea required rows={7} value={resumeText} onChange={(e) => setResumeText(e.target.value)} placeholder="Paste your resume text here…" />
              <Button type="submit" variant="secondary" loading={uploading}>
                Save pasted resume
              </Button>
            </form>
          )}
        </Section>
      </Card>

      <AiKeysCard />

      <AutopilotCard profile={profile} onSaved={(p) => {
        setProfile(p);
        setContextProfile(p);
      }} />

      <DataCard />
    </div>
  );
}

function AutopilotCard({ profile, onSaved }: { profile: ProfileOut; onSaved: (p: ProfileOut) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const save = async (patch: Partial<ProfileOut>) => {
    setBusy(true);
    try {
      const saved = await api.upsertProfile(profilePayload(profile, patch));
      onSaved(saved);
      if (patch.autopilot_enabled !== undefined)
        toast(patch.autopilot_enabled ? "Autopilot on" : "Autopilot off", {
          description: patch.autopilot_enabled
            ? "Each morning Pathlight prepares your best new matches. Nothing is sent without you."
            : undefined,
        });
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : "Couldn't save", { tone: "bad" });
    } finally {
      setBusy(false);
    }
  };
  const on = profile.autopilot_enabled;
  return (
    <Card className="mt-6 p-5 sm:p-7">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-xl">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-[15px] font-semibold text-fg">Autopilot</h2>
            {on && <span className="rounded-md bg-ok-soft px-1.5 py-0.5 text-[11px] font-medium text-ok">On</span>}
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            Every morning, Pathlight takes your best new matches from the past week — up to 3 a day — checks eligibility,
            finds skill gaps and tailors your resume, so they&apos;re waiting in Applications for your review.{" "}
            <strong className="font-medium text-fg">It never applies on its own.</strong>
          </p>
          <label className="mt-4 flex items-center gap-2 text-[13px] text-muted">
            Only jobs matching at least
            <select
              value={profile.autopilot_min_match}
              disabled={busy}
              onChange={(e) => save({ autopilot_min_match: Number(e.target.value) })}
              className="h-8 rounded-lg border border-line-strong bg-surface px-2 text-[13px] font-medium text-fg"
            >
              {[60, 65, 70, 75, 80, 85, 90].map((t) => (
                <option key={t} value={t}>
                  {t}%
                </option>
              ))}
            </select>
          </label>
          {profile.autopilot_last_run && (
            <p className="mt-2 text-xs text-subtle">Last run {profile.autopilot_last_run}.</p>
          )}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label="Autopilot"
          disabled={busy}
          onClick={() => save({ autopilot_enabled: !on })}
          className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-300 ${on ? "bg-ink" : "bg-line-strong"}`}
        >
          <span
            className={`absolute left-0 top-1 h-5 w-5 rounded-full bg-surface shadow transition-transform duration-300 ${on ? "translate-x-6" : "translate-x-1"}`}
            style={{ transitionTimingFunction: "var(--ease-out)" }}
          />
        </button>
      </div>
    </Card>
  );
}

function DataCard() {
  const toast = useToast();
  const { logout } = useRequireAuth();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onExport = async () => {
    setBusy("export");
    try {
      const { blob } = await api.exportAccount();
      saveBlob(blob, "pathlight-data.json");
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : "Export failed", { tone: "bad" });
    } finally {
      setBusy(null);
    }
  };

  const onDelete = async () => {
    setBusy("delete");
    setError(null);
    try {
      await api.deleteAccount();
      logout();
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete your account");
      setBusy(null);
    }
  };

  return (
    <Card className="mt-6 p-5 sm:p-7">
      <h2 className="text-[15px] font-semibold text-fg">Your data</h2>
      <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-muted">
        Download everything Pathlight stores about you, or delete your account. Deleting revokes Gmail access with Google
        and permanently erases your resume, profile and applications.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onExport} loading={busy === "export"}>
          {busy !== "export" && <Download size={14} />} Export my data
        </Button>
        {!confirming && (
          <Button variant="danger" onClick={() => setConfirming(true)}>
            <Trash2 size={14} /> Delete account
          </Button>
        )}
      </div>
      {confirming && (
        <div className="animate-scale-in mt-4 rounded-xl border border-bad/30 bg-bad-soft p-4">
          <p className="text-[13px] font-medium text-bad">This can&apos;t be undone. Type DELETE to confirm.</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <TextInput value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="DELETE" className="sm:max-w-[200px]" autoFocus />
            <Button variant="danger" onClick={onDelete} disabled={typed.trim().toUpperCase() !== "DELETE"} loading={busy === "delete"}>
              Permanently delete
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
          {error && <p className="mt-2 text-xs font-medium text-bad">{error}</p>}
        </div>
      )}
    </Card>
  );
}
