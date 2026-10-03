"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, MailCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { AuthLayout, GoogleButton } from "@/components/AuthLayout";
import { Alert, Button, Field, TextInput } from "@/components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong — please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="We'll email you a link to choose a new one."
      footer={
        <>
          Remembered it?{" "}
          <Link href="/login" className="font-medium text-fg underline decoration-line-strong underline-offset-4 hover:decoration-fg">
            Log in
          </Link>
        </>
      }
    >
      {sent ? (
        <div className="animate-fade-in text-center">
          <span className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-ok-soft text-ok">
            <MailCheck size={20} />
          </span>
          <p className="text-sm leading-relaxed text-muted">
            If <span className="font-medium text-fg">{email}</span> has a Pathlight account, a reset link is on its way. It
            works for 30 minutes — check spam if you don&apos;t see it.
          </p>
        </div>
      ) : (
        <>
          <GoogleButton label="Sign in with Google instead" />
          <form onSubmit={onSubmit} className="space-y-4">
            <Field label="Email">
              <TextInput type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@college.edu" />
            </Field>
            {error && <Alert tone="warn">{error}</Alert>}
            <Button type="submit" size="lg" loading={busy} className="w-full">
              {busy ? "Sending…" : "Send reset link"} {!busy && <ArrowRight size={17} />}
            </Button>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
