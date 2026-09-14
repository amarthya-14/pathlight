"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Code2, TriangleAlert } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { DocumentOut, ProfileOut } from "@/lib/types";
import { Button, Field, PageHeader, SectionLabel, TextArea, TextInput } from "@/components/ui";

export default function ProfilePage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [cgpa, setCgpa] = useState("");
  const [branch, setBranch] = useState("");
  const [githubUsername, setGithubUsername] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);

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
    setSaveMessage(null);
    setError(null);
    try {
      const p = await api.upsertProfile({
        cgpa: cgpa ? Number(cgpa) : null,
        branch: branch || null,
        github_username: githubUsername || null,
      });
      setProfile(p);
      setSaveMessage("Saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const onUploadResume = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    setError(null);
    try {
      await api.pasteDocument({ doc_type: "resume", title: "Resume", text: resumeText });
      setResumeText("");
      loadDocuments();
      setSaveMessage("Resume indexed. Skill Gap results will now use it as real evidence.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to upload resume");
    } finally {
      setUploading(false);
    }
  };

  if (authLoading || !user) return null;
  if (!profile) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  const hasResume = documents.some((d) => d.doc_type === "resume");

  return (
    <div className="animate-fade-in max-w-xl space-y-10">
      <PageHeader title="Profile" subtitle="Used by Eligibility and Skill Gap checks." />

      <section>
        <SectionLabel>Academic details</SectionLabel>
        <form onSubmit={onSaveProfile} className="card-shadow space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <Field label="CGPA">
            <TextInput type="number" step="0.01" min="0" max="10" value={cgpa} onChange={(e) => setCgpa(e.target.value)} />
          </Field>
          <Field label="Branch">
            <TextInput type="text" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="CSE" />
          </Field>
          <Field
            label="GitHub username (optional)"
            hint="Used by Skill Gap as supplementary evidence from your public repos — never changes the matched/weak/missing verdict itself, only adds corroborating detail."
          >
            <div className="relative">
              <Code2 size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <TextInput
                type="text"
                value={githubUsername}
                onChange={(e) => setGithubUsername(e.target.value)}
                placeholder="octocat"
                className="pl-9"
              />
            </div>
          </Field>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </form>
      </section>

      <section>
        <SectionLabel>Resume</SectionLabel>
        <div className="card-shadow space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          {hasResume ? (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3.5 py-2.5 text-sm font-medium text-emerald-700">
              <CheckCircle2 size={16} /> A resume is on file and indexed for Skill Gap matching.
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm font-medium text-amber-800">
              <TriangleAlert size={16} /> No resume on file — Skill Gap results will show every skill as missing.
            </div>
          )}
          <form onSubmit={onUploadResume} className="space-y-3">
            <TextArea
              required
              rows={6}
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste your resume text here…"
            />
            <Button type="submit" variant="secondary" disabled={uploading}>
              {uploading ? "Uploading…" : "Add / replace resume"}
            </Button>
          </form>
        </div>
      </section>

      {saveMessage && <p className="text-sm font-medium text-emerald-600">{saveMessage}</p>}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </div>
  );
}
