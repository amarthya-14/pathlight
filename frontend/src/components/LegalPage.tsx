import Link from "next/link";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "";

export function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-5">
          <Brand />
          <ThemeToggle />
        </div>
      </header>
      <main className="page-enter mx-auto max-w-3xl px-5 py-14">
        <h1 className="text-[2rem] font-semibold tracking-[-0.03em] text-fg">{title}</h1>
        <p className="mt-2 text-[13px] text-subtle">Last updated {updated}</p>
        <div className="legal mt-10 space-y-8 text-[15px] leading-relaxed text-muted">{children}</div>
        <div className="mt-14 flex gap-5 border-t border-line pt-6 text-[13px] text-subtle">
          <Link href="/privacy" className="hover:text-fg">Privacy</Link>
          <Link href="/terms" className="hover:text-fg">Terms</Link>
          <Link href="/" className="hover:text-fg">Home</Link>
        </div>
      </main>
    </div>
  );
}

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-[17px] font-semibold text-fg">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
