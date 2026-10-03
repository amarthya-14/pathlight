"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { FullScreenLoader } from "@/components/Shell";

// Landing spot after "Continue with Google": the backend puts the session token in the
// URL fragment (never sent to any server), we store it and move on.
export default function AuthCallbackPage() {
  const router = useRouter();
  const { refresh } = useAuth();

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    window.history.replaceState(null, "", window.location.pathname); // drop the token from the address bar
    if (!token) {
      router.replace("/login?google=error");
      return;
    }
    setToken(token);
    refresh().then(() => router.replace("/dashboard"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <FullScreenLoader />;
}
