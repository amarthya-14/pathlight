import type { Metadata } from "next";
import { CONTACT_EMAIL, LegalPage, LegalSection } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="3 October 2026">
      <p>
        Pathlight helps students find jobs, check eligibility and prepare applications. This page explains what we
        collect, why, and the control you have. We don&apos;t sell your data, and we don&apos;t show ads.
      </p>

      <LegalSection title="What we collect">
        <ul className="list-disc space-y-2 pl-5">
          <li><strong className="text-fg">Account:</strong> your name, email and a hashed password (or your Google account&apos;s name and email if you sign in with Google).</li>
          <li><strong className="text-fg">Profile:</strong> college, graduation year, branch, CGPA, experience, target roles, locations and the application preferences you enter.</li>
          <li><strong className="text-fg">Resume:</strong> the file you upload and the text and links read from it.</li>
          <li><strong className="text-fg">Applications:</strong> jobs you track, eligibility and skill-gap results, tailored resumes, cover notes and status updates.</li>
          <li><strong className="text-fg">Gmail (only if you connect it):</strong> job-alert emails from LinkedIn and Naukri alert senders. Pathlight never reads any other email. If you approve an application by email, it&apos;s sent from your account.</li>
        </ul>
      </LegalSection>

      <LegalSection title="How we use it">
        <p>Only to provide Pathlight to you: matching jobs to your resume, checking eligibility, tailoring your resume and cover note, preparing application answers, and sending applications you explicitly approve. Pathlight never applies on your behalf without your approval.</p>
        <p>To do this, the relevant text (your resume and the job description) is processed by Google&apos;s Gemini AI service. Pathlight currently uses Gemini&apos;s free tier, under whose terms Google may use submitted content to improve its services — so only put on your resume what you&apos;d share with an employer. Pathlight itself never uses your data to train models.</p>
      </LegalSection>

      <LegalSection title="Google user data">
        <p>
          Pathlight&apos;s use and transfer of information received from Google APIs adheres to the{" "}
          <a className="text-fg underline underline-offset-2" href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements. Gmail data is used only to find job alerts and send applications you approve; it is not used for ads, sold, or read by people except where you ask us to help with a problem, for security, or where the law requires.
        </p>
        <p>Access tokens are encrypted at rest. Disconnecting Gmail (or deleting your account) revokes Pathlight&apos;s access with Google immediately.</p>
      </LegalSection>

      <LegalSection title="Who processes it">
        <p>Our service providers, only to run Pathlight: MongoDB Atlas (database), Render (backend hosting), Vercel (website hosting), and Google (sign-in, Gmail and Gemini AI). Job listings come from public job boards; we don&apos;t send them your data.</p>
      </LegalSection>

      <LegalSection title="Your rights">
        <p>Under India&apos;s Digital Personal Data Protection Act, 2023 you can access, correct and erase your data. In Pathlight: edit anything in Profile, download everything we hold with <strong className="text-fg">Profile → Your data → Export</strong>, and erase your account and all its data with <strong className="text-fg">Delete account</strong> — deletion is immediate and permanent.</p>
      </LegalSection>

      <LegalSection title="Retention and security">
        <p>We keep your data while your account exists and delete it when you delete your account. Passwords are hashed with bcrypt, connections use HTTPS, and Gmail tokens are encrypted.</p>
      </LegalSection>

      {CONTACT_EMAIL && (
        <LegalSection title="Contact">
          <p>Questions or requests: <a className="text-fg underline underline-offset-2" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
        </LegalSection>
      )}
    </LegalPage>
  );
}
