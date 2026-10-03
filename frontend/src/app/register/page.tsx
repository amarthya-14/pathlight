"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthLayout, GoogleButton, PasswordInput } from "@/components/AuthLayout";
import { Alert, Button, Field, TextInput } from "@/components/ui";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const { user, refresh } = useAuth();

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.register(email, password, name);
      await api.login(email, password);
      await refresh();
      router.push("/welcome");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  const longEnough = password.length >= 8;

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Free for students. Takes two minutes — then jobs start finding you."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-fg underline decoration-line-strong underline-offset-4 hover:decoration-fg">
            Log in
          </Link>
        </>
      }
    >
      <GoogleButton label="Sign up with Google" />
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Your name">
          <TextInput
            name="full_name"
            required
            autoComplete="name"
            autoFocus
            placeholder="Asha Rao"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Email">
          <TextInput
            type="email"
            required
            autoComplete="email"
            placeholder="you@college.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password">
          <PasswordInput
            required
            minLength={8}
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className={`mt-2 flex items-center gap-1.5 text-xs transition-colors ${longEnough ? "text-ok" : "text-subtle"}`}>
            <Check size={13} strokeWidth={2.6} /> At least 8 characters
          </p>
        </Field>
        {error && <Alert tone="bad">{error}</Alert>}
        <Button type="submit" size="lg" loading={submitting} className="w-full">
          {submitting ? "Creating account…" : "Create account"}
          {!submitting && <ArrowRight size={17} />}
        </Button>
        <p className="text-center text-xs leading-relaxed text-subtle">
          By creating an account you agree to the{" "}
          <Link href="/terms" className="underline underline-offset-2 hover:text-fg">Terms</Link> and{" "}
          <Link href="/privacy" className="underline underline-offset-2 hover:text-fg">Privacy Policy</Link>.
        </p>
      </form>
    </AuthLayout>
  );
}
