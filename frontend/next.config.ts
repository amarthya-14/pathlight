import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Backend base URL is read at runtime from NEXT_PUBLIC_API_URL (see src/lib/api.ts)
  // rather than baked in here — matches .env.example's existing variable.

  // Explicit: a stray package-lock.json at ~/package-lock.json (outside this repo)
  // otherwise makes Turbopack guess the wrong workspace root and warn about it.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
