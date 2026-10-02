"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Code2, FileText, GraduationCap, Loader2, Save, UploadCloud } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { DocumentOut, ProfileOut } from "@/lib/types";
import { Alert, Button, Card, Field, PageHeader, PageSkeleton, TextArea, TextInput } from "@/components/ui";

const BRANCHES = ["CSE", "IT", "AI & DS", "AI & ML", "ECE", "EEE", "EIE", "ME", "CE", "Chemical", "Biotech"];

export default function ProfilePage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [cgpa, setCgpa] = useState("");
  const [branch, setBranch] = useState("");
  const [githubUsername, setGithubUsername] = useState("");
  const [saving, setSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [resumeMessage, setResumeMessage] = useState<string | null>(null);
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
      setGithubUsername(p.github_username ?? "");
    });
    loadDocuments();
  }, [user]);

  const onSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setProfileMessage(null);
    setError(null);
    try {
      setProfile(
        await api.upsertProfile({
          cgpa: cgpa ? Number(cgpa) : null,
          branch: branch || null,
          github_username: githubUsername || null,
        })
      );
      setProfileMessage("Saved — eligibility checks will use these details.");
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
    setResumeMessage(null);
    try {
      const doc = await api.uploadDocument(file, "resume");
      loadDocuments();
      if (!doc.extracted_text || !doc.extracted_text.trim()) {
        setResumeError(
          "Uploaded, but no text could be read from this file (likely a scanned/image PDF). Export your resume as a text-based PDF, or paste the text instead."
        );
      } else {
        setResumeMessage("Resume uploaded and indexed. Open any application and click “Generate tailored resume”.");
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
      setResumeMessage("Resume saved and indexed. Skill Gap results now use it as real evidence.");
    } catch (err) {
      setResumeError(err instanceof ApiError ? err.detail : "Failed to save resume");
    } finally {
      setUploading(false);
    }
  };

  if (authLoading || !user) return null;
  if (!profile) return <PageSkeleton />;

  const latestResume = documents.find((d) => d.doc_type === "resume"); // list is newest-first
  const completeness = [Boolean(profile.cgpa), Boolean(profile.branch), Boolean(latestResume), Boolean(profile.github_username)].filter(Boolean).length;

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <PageHeader
          eyebrow="You"
          title="Profile"
          subtitle="Your details power eligibility checks, skill gaps and tailored resumes."
          actions={
            <div className="glass flex items-center gap-3 rounded-xl px-3.5 py-2">
              <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-brand-gradient transition-all duration-700" style={{ width: `${completeness * 25}%` }} />
              </div>
              <span className="text-xs font-medium text-muted">{completeness * 25}% complete</span>
            </div>
          }
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <Card className="animate-fade-in p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-fg">
              <GraduationCap size={19} />
            </span>
            <div>
              <div className="font-semibold text-fg">Academic details</div>
              <div className="text-xs text-muted">Used to check eligibility criteria</div>
            </div>
          </div>
          <form onSubmit={onSaveProfile} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
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
            <Field
              label="GitHub username (optional)"
              hint="Adds supporting evidence from your public repos to Skill Gap — it never changes the verdict itself."
            >
              <div className="relative">
                <Code2 size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle" />
                <TextInput type="text" value={githubUsername} onChange={(e) => setGithubUsername(e.target.value)} placeholder="octocat" className="pl-10" />
              </div>
            </Field>
            {profileMessage && <Alert tone="ok">{profileMessage}</Alert>}
            {error && <Alert tone="bad">{error}</Alert>}
            <Button type="submit" loading={saving} className="w-full sm:w-auto">
              {!saving && <Save size={15} />} {saving ? "Saving…" : "Save details"}
            </Button>
          </form>
        </Card>

        <Card className="animate-fade-in p-5 sm:p-6" style={{ animationDelay: "0.06s" }}>
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-fg">
              <FileText size={19} />
            </span>
            <div>
              <div className="font-semibold text-fg">Resume</div>
              <div className="text-xs text-muted">The single source of truth for tailoring — we never add to it</div>
            </div>
          </div>

          {latestResume ? (
            <div className="mb-4 flex items-center gap-3 rounded-xl border border-ok/20 bg-ok-soft px-4 py-3">
              <CheckCircle2 size={18} className="shrink-0 text-ok" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-fg">{latestResume.original_filename}</div>
                <div className="text-xs text-muted">
                  In use since {new Date(latestResume.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
                </div>
              </div>
            </div>
          ) : (
            <Alert tone="warn" className="mb-4">
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
            className={`group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-5 py-9 text-center transition-all ${
              dragging ? "scale-[1.01] border-accent bg-accent-soft" : "border-line-strong bg-surface-2 hover:border-accent/60 hover:bg-accent-soft/50"
            }`}
          >
            <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow transition-transform group-hover:-translate-y-0.5">
              {uploading ? <Loader2 size={22} className="animate-spin" /> : <UploadCloud size={22} />}
            </span>
            <span className="text-sm font-semibold text-fg">
              {uploading ? "Uploading & indexing…" : latestResume ? "Drop a new resume to replace it" : "Drop your resume here"}
            </span>
            <span className="mt-1 text-xs text-muted">
              or <span className="font-semibold text-accent-fg">browse</span> · PDF or TXT, up to 10MB · text-based PDFs only
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

          {resumeMessage && <Alert tone="ok" className="mt-4">{resumeMessage}</Alert>}
          {resumeError && <Alert tone="bad" className="mt-4">{resumeError}</Alert>}

          <button
            type="button"
            onClick={() => setShowPaste((v) => !v)}
            className="mt-4 text-xs font-medium text-muted underline-offset-4 hover:text-fg hover:underline"
          >
            {showPaste ? "Hide text paste" : "Or paste resume text instead"}
          </button>
          {showPaste && (
            <form onSubmit={onPasteResume} className="animate-fade-in mt-3 space-y-3">
              <TextArea required rows={7} value={resumeText} onChange={(e) => setResumeText(e.target.value)} placeholder="Paste your resume text here…" />
              <Button type="submit" variant="secondary" loading={uploading}>
                Save pasted resume
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
