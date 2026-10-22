"use client";

import { Landmark } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { profilePayload } from "@/lib/profile";
import type { PlacementPolicy, ProfileOut } from "@/lib/types";
import { useToast } from "./Toast";
import { Button, Card, Field, TextInput } from "./ui";

const AFTER_OFFER: { value: PlacementPolicy["after_offer"]; label: string }[] = [
  { value: "higher_tier", label: "Only higher-tier drives (e.g. dream → super dream)" },
  { value: "stop", label: "No more drives — one offer per student" },
  { value: "any", label: "No restriction" },
];

const num = (v: string) => (v.trim() === "" ? null : Number(v));

// The college's own offer rules. They differ by college and year, so the student enters them;
// Pathlight then applies them to on-campus drives in eligibility (backend app/core/placement.py).
export function PlacementRulesCard({ profile, onSaved }: { profile: ProfileOut; onSaved: (p: ProfileOut) => void }) {
  const toast = useToast();
  const policy = profile.placement_policy;
  const [dream, setDream] = useState(policy?.dream_min_lpa?.toString() ?? "");
  const [superDream, setSuperDream] = useState(policy?.super_dream_min_lpa?.toString() ?? "");
  const [afterOffer, setAfterOffer] = useState<PlacementPolicy["after_offer"]>(policy?.after_offer ?? "higher_tier");
  const [offerCompany, setOfferCompany] = useState(profile.current_offer?.company ?? "");
  const [offerCtc, setOfferCtc] = useState(profile.current_offer?.ctc_lpa?.toString() ?? "");
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const placement_policy =
        dream || superDream || afterOffer !== "higher_tier"
          ? { dream_min_lpa: num(dream), super_dream_min_lpa: num(superDream), after_offer: afterOffer }
          : null;
      const current_offer = offerCompany.trim() && offerCtc ? { company: offerCompany.trim(), ctc_lpa: Number(offerCtc) } : null;
      onSaved(await api.upsertProfile(profilePayload(profile, { placement_policy, current_offer })));
      toast("Placement rules saved", { description: "Use “Re-check” on an application to apply them to it." });
    } catch (err) {
      toast(err instanceof ApiError ? err.detail : "Couldn't save", { tone: "bad" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="mt-6 p-5 sm:p-7">
      <form onSubmit={save} className="space-y-4">
        <div className="max-w-xl">
          <div className="flex items-center gap-2">
            <Landmark size={16} className="text-accent" />
            <h2 className="text-[15px] font-semibold text-fg">Campus placement rules</h2>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            Your college&apos;s rules for students who already hold an offer. Pathlight applies them to on-campus drives
            only, so it can tell you when a drive is closed to you. Check your placement policy document for the numbers.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Dream offer from (LPA)" hint="e.g. 5.5">
            <TextInput type="number" step="0.1" min="0" value={dream} onChange={(e) => setDream(e.target.value)} placeholder="5.5" />
          </Field>
          <Field label="Super dream from (LPA)" hint="e.g. 10">
            <TextInput type="number" step="0.1" min="0" value={superDream} onChange={(e) => setSuperDream(e.target.value)} placeholder="10" />
          </Field>
        </div>
        <Field label="Once you hold an offer">
          <select
            value={afterOffer}
            onChange={(e) => setAfterOffer(e.target.value as PlacementPolicy["after_offer"])}
            className="h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-fg shadow-xs focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
          >
            {AFTER_OFFER.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Offer you hold (company)" hint="Leave empty if you don't have one yet.">
            <TextInput value={offerCompany} onChange={(e) => setOfferCompany(e.target.value)} placeholder="Infosys" />
          </Field>
          <Field label="Its CTC (LPA)">
            <TextInput type="number" step="0.1" min="0" value={offerCtc} onChange={(e) => setOfferCtc(e.target.value)} placeholder="7" />
          </Field>
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={busy}>
            {busy ? "Saving…" : "Save rules"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
