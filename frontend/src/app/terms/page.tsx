import type { Metadata } from "next";
import { CONTACT_EMAIL, LegalPage, LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Use" updated="3 October 2026">
      <p>By using Pathlight you agree to these terms. They&apos;re short on purpose.</p>

      <LegalSection title="What Pathlight does — and doesn't">
        <p>Pathlight suggests jobs, checks eligibility, tailors your resume and prepares applications. It doesn&apos;t guarantee interviews or offers, and job listings come from third parties — always confirm details on the employer&apos;s own posting.</p>
        <p>Pathlight only sends an application when you approve it. On sites like LinkedIn you submit yourself; Pathlight never logs into those sites for you.</p>
      </LegalSection>

      <LegalSection title="Your responsibilities">
        <ul className="list-disc space-y-2 pl-5">
          <li>Everything in your resume and applications must be true. Pathlight is built never to add skills you don&apos;t have; if you edit a tailored resume, what you add is your responsibility.</li>
          <li>Review every application before approving it.</li>
          <li>Keep your account secure and don&apos;t use Pathlight to spam employers or misuse anyone&apos;s data.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Fair use">
        <p>Pathlight is free for students. To keep it that way, AI-heavy actions have daily limits, and we may suspend accounts that abuse the service.</p>
      </LegalSection>

      <LegalSection title="Availability and liability">
        <p>Pathlight is provided as is. We work to keep it reliable and accurate, but we&apos;re not liable for missed deadlines, application outcomes, or decisions made using its suggestions.</p>
      </LegalSection>

      <LegalSection title="Ending">
        <p>You can delete your account at any time in Profile. We may update these terms; significant changes will be announced in the app.</p>
        {CONTACT_EMAIL && (
          <p>Contact: <a className="text-fg underline underline-offset-2" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
        )}
      </LegalSection>
    </LegalPage>
  );
}
