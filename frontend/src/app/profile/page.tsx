"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Code2, FileText, Loader2, UploadCloud } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { DocumentOut, ProfileOut } from "@/lib/types";
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

export default function ProfilePage() {
  const { user, loading: authLoading } = useRequireAuth();
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
    api.getProfile().then((p) => {
      setProfile(p);
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
      setProfile(
        await api.upsertProfile({
          cgpa: cgpa ? Number(cgpa) : null,
          branch: branch || null,
          github_username: githubUsername || null,
          experience_years: Number(experience),
        })
      );
      toast("Profile saved", { description: "Use “Re-check” on an application to apply the new details to it." });
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
  const completeness = [Boolean(profile.cgpa), Boolean(profile.branch), profile.experience_years !== null, Boolean(latestResume)].filter(Boolean).length;

  return (
    <div className="max-w-4xl">
      <div className="animate-fade-in">
        <PageHeader
          title="Profile"
          subtitle="Your details power eligibility checks, skill gaps and tailored resumes."
          actions={
            <div className="flex items-center gap-3 text-[13px] text-muted">
              <Progress value={completeness * 25} tone="ok" className="w-24" />
              {completeness * 25}% complete
            </div>
          }
        />
      </div>

      <Card className="p-5 sm:p-7">
        <Section title="Academic details" description="Checked against each posting's CGPA, branch and experience requirements.">
          <form onSubmit={onSaveProfile} className="space-y-4">
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
          </form>
        </Section>

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
    </div>
  );
}
