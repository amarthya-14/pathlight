"use client";

import { useState } from "react";
import { ArrowUp, ArrowUpRight, Check, Eye, EyeOff, KeyRound, Plus, ShieldCheck, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AiKeyOut, AiProviderId } from "@/lib/types";
import { useToast } from "./Toast";
import { Button, Card, cx, Field, TextInput } from "./ui";

type Guide = {
  id: AiProviderId;
  name: string;
  tag: string;
  blurb: string;
  url?: string;
  cta?: string;
  steps: React.ReactNode[];
  note: string;
  placeholder: string;
};

// What each provider needs, in plain steps. Google AI Studio first: free, no card, and the
// same models Pathlight already uses.
const GUIDES: Guide[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    tag: "Free · Recommended",
    blurb: "Same models Pathlight uses. No card needed.",
    url: "https://aistudio.google.com/apikey",
    cta: "Open Google AI Studio",
    steps: [
      <>Open Google AI Studio and sign in with a <strong>personal</strong> Google account (college accounts often block it).</>,
      <>Click <strong>Create API key</strong>. If it asks, choose <strong>Create API key in new project</strong>.</>,
      <>Copy the key — it starts with <code>AIza</code> or <code>AQ.</code> — and paste it below.</>,
    ],
    note: "Free tier, resets daily (around 12:30–1:30 PM IST). On the free tier, Google may use prompts to improve its products.",
    placeholder: "AIza… or AQ.…",
  },
  {
    id: "groq",
    name: "Groq",
    tag: "Free · Fastest",
    blurb: "Very fast open models like Llama.",
    url: "https://console.groq.com/keys",
    cta: "Open Groq Console",
    steps: [
      <>Open the Groq Console and sign in (Google sign-in works).</>,
      <>Click <strong>Create API Key</strong> and name it “Pathlight”.</>,
      <>Copy the key — it starts with <code>gsk_</code> and is shown only once.</>,
    ],
    note: "Free tier with daily limits. Great as a second key alongside Gemini.",
    placeholder: "gsk_…",
  },
  {
    id: "openai",
    name: "OpenAI",
    tag: "Paid",
    blurb: "GPT models. Billed per use.",
    url: "https://platform.openai.com/api-keys",
    cta: "Open OpenAI Platform",
    steps: [
      <>Sign in to the OpenAI Platform.</>,
      <>Add a payment method or credits under <strong>Billing</strong> — the API isn&apos;t free.</>,
      <>Go to <strong>API keys → Create new secret key</strong>, then copy it (starts with <code>sk-</code>).</>,
    ],
    note: "Paid per use. Set a monthly cap under Billing → Limits so there are no surprises.",
    placeholder: "sk-…",
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    tag: "Paid",
    blurb: "Claude models. Billed per use.",
    url: "https://console.anthropic.com/settings/keys",
    cta: "Open Anthropic Console",
    steps: [
      <>Sign in to the Anthropic Console.</>,
      <>Add credits under <strong>Billing</strong>.</>,
      <>Click <strong>Create Key</strong> and copy it (starts with <code>sk-ant-</code>).</>,
    ],
    note: "Paid per use. You can set spend limits in the Console.",
    placeholder: "sk-ant-…",
  },
  {
    id: "custom",
    name: "Other",
    tag: "Any OpenAI-compatible",
    blurb: "OpenRouter, DeepSeek, Together, Mistral…",
    steps: [
      <>Create an API key in your provider&apos;s dashboard.</>,
      <>Find its OpenAI-compatible <strong>base URL</strong> (e.g. <code>https://openrouter.ai/api/v1</code>) and a <strong>model</strong> name.</>,
      <>Paste all three below.</>,
    ],
    note: "The model must support tool/function calling.",
    placeholder: "Your API key",
  },
];

const NAME: Record<AiProviderId, string> = Object.fromEntries(GUIDES.map((g) => [g.id, g.name])) as Record<AiProviderId, string>;
const HUE: Record<AiProviderId, number> = { gemini: 220, groq: 18, openai: 160, anthropic: 28, custom: 270 };

function ProviderMark({ id }: { id: AiProviderId }) {
  return (
    <span
      className="avatar-tint flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs font-semibold"
      style={{ "--h": HUE[id] } as React.CSSProperties}
      aria-hidden
    >
      {NAME[id].slice(0, 1)}
    </span>
  );
}

function ordinal(i: number) {
  return ["1st", "2nd", "3rd", "4th", "5th"][i] ?? `${i + 1}th`;
}

// "Your AI keys": Pathlight works without one (shared free key), but a student's own key
// means higher daily limits and no waiting on the shared quota. Keys are checked with the
// provider before saving and stored encrypted; only the last 4 characters come back.
export function AiKeysCard() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const keys = user?.ai_keys ?? [];
  const [adding, setAdding] = useState(false);
  const [provider, setProvider] = useState<AiProviderId>("gemini");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;
  const guide = GUIDES.find((g) => g.id === provider)!;
  const update = (next: AiKeyOut[]) => setUser({ ...user, ai_keys: next });

  const reset = () => {
    setApiKey("");
    setBaseUrl("");
    setModel("");
    setShowKey(false);
    setError(null);
  };

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("connect");
    setError(null);
    try {
      const res = await api.addAiKey({
        provider,
        api_key: apiKey.trim(),
        base_url: provider === "custom" ? baseUrl.trim() : null,
        model: model.trim() || null,
      });
      update(res.ai_keys);
      toast(res.message || "Key connected");
      reset();
      setAdding(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't check that key — try again.");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: AiProviderId) => {
    setBusy(`remove:${id}`);
    try {
      update((await api.removeAiKey(id)).ai_keys);
      toast(`${NAME[id]} key removed`, { tone: "info" });
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : "Couldn't remove the key", { tone: "bad" });
    } finally {
      setBusy(null);
    }
  };

  const moveFirst = async (id: AiProviderId) => {
    setBusy(`order:${id}`);
    try {
      update((await api.reorderAiKeys([id, ...keys.map((k) => k.provider).filter((p) => p !== id)])).ai_keys);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="mt-6 overflow-hidden">
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between sm:p-7">
        <div className="max-w-xl">
          <div className="flex items-center gap-2">
            <KeyRound size={16} className="text-accent" />
            <h2 className="text-[15px] font-semibold text-fg">Your AI keys</h2>
            <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] font-medium text-muted">Optional</span>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            Pathlight works without one — it runs on a shared free key. Add your own to get{" "}
            <strong className="font-medium text-fg">4× the daily limits</strong> and never wait on the shared quota. If your
            key runs out, Pathlight quietly falls back to the shared one.
          </p>
        </div>
        {!adding && (
          <Button variant={keys.length ? "secondary" : "primary"} onClick={() => setAdding(true)} className="shrink-0">
            <Plus size={14} /> Add a key
          </Button>
        )}
      </div>

      {keys.length > 0 && (
        <ul className="divide-y divide-line border-t border-line">
          {keys.map((k, i) => (
            <li key={k.provider} className="flex items-center gap-3 px-5 py-3.5 sm:px-7">
              <ProviderMark id={k.provider} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-[13.5px] font-medium text-fg">
                  {NAME[k.provider]}
                  <span className="font-mono text-xs font-normal text-subtle">••••{k.last4}</span>
                  <span className={cx("rounded-md px-1.5 py-0.5 text-[11px] font-medium", i === 0 ? "bg-ok-soft text-ok" : "bg-surface-2 text-muted")}>
                    Used {ordinal(i)}
                  </span>
                </div>
                <div className="truncate text-xs text-subtle">
                  {k.strong_model}
                  {k.small_model !== k.strong_model && ` · fast: ${k.small_model}`}
                </div>
              </div>
              {i > 0 && (
                <button
                  onClick={() => moveFirst(k.provider)}
                  disabled={busy !== null}
                  title="Use this first"
                  aria-label={`Use ${NAME[k.provider]} first`}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-subtle transition-colors hover:bg-surface-hover hover:text-fg"
                >
                  <ArrowUp size={14} />
                </button>
              )}
              <button
                onClick={() => remove(k.provider)}
                disabled={busy !== null}
                aria-label={`Remove ${NAME[k.provider]} key`}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-subtle transition-colors hover:bg-bad-soft hover:text-bad"
              >
                <X size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {adding && (
        <div className="animate-fade-in border-t border-line bg-surface-2/50 p-5 sm:p-7">
          <div className="text-[13px] font-medium text-fg">Choose a provider</div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" role="radiogroup" aria-label="AI provider">
            {GUIDES.map((g) => {
              const connected = keys.some((k) => k.provider === g.id);
              const selected = provider === g.id;
              return (
                <button
                  key={g.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => {
                    setProvider(g.id);
                    setError(null);
                  }}
                  className={cx(
                    "rounded-xl border p-3 text-left transition-[border-color,background-color,box-shadow] duration-200",
                    selected ? "border-ink bg-surface shadow-xs ring-1 ring-ink" : "border-line bg-surface hover:border-line-strong"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-semibold text-fg">{g.name}</span>
                    {connected && <Check size={13} className="text-ok" strokeWidth={2.6} />}
                  </div>
                  <div className={cx("mt-0.5 text-[11px] font-medium", g.tag.startsWith("Free") ? "text-ok" : "text-subtle")}>{g.tag}</div>
                  <div className="mt-1.5 text-[11.5px] leading-snug text-muted">{g.blurb}</div>
                </button>
              );
            })}
          </div>

          <div key={guide.id} className="step-forward mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
            <div>
              <div className="text-[13px] font-medium text-fg">How to get a {guide.name} key</div>
              <ol className="mt-3 space-y-3">
                {guide.steps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-[13px] leading-relaxed text-muted">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink text-[10.5px] font-semibold text-ink-fg">
                      {i + 1}
                    </span>
                    <span className="[&_code]:rounded [&_code]:bg-surface-hover [&_code]:px-1 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-fg [&_strong]:font-medium [&_strong]:text-fg">
                      {step}
                    </span>
                  </li>
                ))}
              </ol>
              {guide.url && (
                <a
                  href={guide.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3.5 text-[13px] font-medium text-fg shadow-xs transition-colors hover:bg-surface-hover"
                >
                  {guide.cta} <ArrowUpRight size={14} />
                </a>
              )}
              <p className="mt-4 text-xs leading-relaxed text-subtle">{guide.note}</p>
            </div>

            <form onSubmit={connect} className="space-y-4">
              <Field label={`${guide.name} API key`}>
                <div className="relative">
                  <TextInput
                    type={showKey ? "text" : "password"}
                    required
                    autoComplete="off"
                    spellCheck={false}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={guide.placeholder}
                    className="pr-10 font-mono text-[13px]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((v) => !v)}
                    aria-label={showKey ? "Hide key" : "Show key"}
                    className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-subtle hover:text-fg"
                  >
                    {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </Field>
              {provider === "custom" && (
                <Field label="Base URL">
                  <TextInput required value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://openrouter.ai/api/v1" />
                </Field>
              )}
              {provider !== "gemini" && (
                <Field
                  label={provider === "custom" ? "Model" : "Model (optional)"}
                  hint={provider === "custom" ? undefined : "Leave empty and Pathlight picks the best model your key can use."}
                >
                  <TextInput required={provider === "custom"} value={model} onChange={(e) => setModel(e.target.value)} placeholder={provider === "custom" ? "e.g. deepseek-chat" : "Automatic"} />
                </Field>
              )}
              {error && <p className="rounded-lg bg-bad-soft px-3 py-2 text-[13px] text-bad">{error}</p>}
              <div className="flex items-center gap-2">
                <Button type="submit" loading={busy === "connect"} disabled={!apiKey.trim()}>
                  {busy === "connect" ? "Checking with " + guide.name + "…" : "Connect"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    reset();
                    setAdding(false);
                  }}
                >
                  Cancel
                </Button>
              </div>
              <p className="flex items-start gap-1.5 text-xs leading-relaxed text-subtle">
                <ShieldCheck size={13} className="mt-[1px] shrink-0 text-ok" />
                Checked with {guide.name} before saving, stored encrypted, used only for your requests. Remove it anytime.
              </p>
            </form>
          </div>
        </div>
      )}
    </Card>
  );
}
