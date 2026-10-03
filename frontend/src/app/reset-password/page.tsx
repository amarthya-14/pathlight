"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthLayout, PasswordInput } from "@/components/AuthLayout";
import { Alert, Button, Field } from "@/components/ui";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [token, setTokenValue] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // The link carries its token in the fragment, so it never reaches server logs.
    setTokenValue(new URLSearchParams(window.location.hash.slice(1)).get("token"));
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't reset your password.");
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="You'll be signed in right after."
      footer={
        <Link href="/forgot-password" className="font-medium text-fg underline decoration-line-strong underline-offset-4 hover:decoration-fg">
          Send a new link
        </Link>
      }
    >
      {token === null ? (
        <Alert tone="warn">This page needs the link from your reset email. Request a new one below.</Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="New password">
            <PasswordInput required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
            <p className={`mt-2 flex items-center gap-1.5 text-xs transition-colors ${password.length >= 8 ? "text-ok" : "text-subtle"}`}>
              <Check size={13} strokeWidth={2.6} /> At least 8 characters
            </p>
          </Field>
          {error && <Alert tone="bad">{error}</Alert>}
          <Button type="submit" size="lg" loading={busy} className="w-full">
            {busy ? "Saving…" : "Save and sign in"} {!busy && <ArrowRight size={17} />}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
