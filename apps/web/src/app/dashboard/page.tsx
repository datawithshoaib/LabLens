import Link from "next/link";

import { auth, authProviderEnabled, preferredProvider, signIn } from "@/auth";
import ReportDashboard from "@/app/dashboard/report-dashboard";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const session = await auth();
  if (!session) {
    if (!authProviderEnabled) {
      return (
        <main className="dashboard-page">
          <Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">L</span><span>LabLens</span></Link>
          <section className="dashboard-intro">
            <p className="eyebrow">SECURE REPORT SPACE</p>
            <h1>Sign-in is not configured yet.</h1>
            <p>Configure an OIDC identity provider and the server secrets before enabling report access.</p>
          </section>
        </main>
      );
    }
    return (
      <main className="dashboard-page">
        <Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">L</span><span>LabLens</span></Link>
        <section className="dashboard-intro">
          <p className="eyebrow">SECURE REPORT SPACE</p>
          <h1>Sign in to your reports.</h1>
          <form action={async () => { "use server"; await signIn(preferredProvider, { redirectTo: "/dashboard" }); }}>
            <button className="primary-button" type="submit">Continue securely <span aria-hidden="true">↗</span></button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">L</span><span>LabLens</span></Link>
        <span className="private-label">Private report space</span>
      </header>
      <section className="dashboard-intro">
        <p className="eyebrow">YOUR REPORTS</p>
        <h1>A place to review, carefully.</h1>
        <p>Reports are private to your account. Entered values must be checked against the original report before a range comparison is confirmed.</p>
      </section>
      <ReportDashboard />
      <p className="dashboard-safety">LabLens is educational and does not diagnose or recommend treatment. A clinician should interpret results in context.</p>
    </main>
  );
}
