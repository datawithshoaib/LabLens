import Link from "next/link";

import AuthControl from "@/app/auth-control";

export default function Home() {
  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="LabLens home">
          <span className="brand-mark" aria-hidden="true">L</span>
          <span>LabLens</span>
        </a>
        <nav className="top-actions" aria-label="Main navigation">
          <a className="top-link" href="#how-it-works">How it works</a>
          <AuthControl />
        </nav>
      </header>

      <section className="hero" id="home" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> A clearer way to read your report</p>
          <h1 id="hero-title">Understand the numbers.<br /><em>Prepare for the conversation.</em></h1>
          <p className="hero-description">
            LabLens is being built to explain the terms and reference ranges on a lab report in plain language, so you can have a more informed conversation with your clinician.
          </p>
          <Link className="primary-button" href="/dashboard">Open your secure dashboard <span aria-hidden="true">↗</span></Link>
          <p className="quiet-note">No diagnosis. No treatment advice. Just clearer explanations.</p>
        </div>
        <aside className="report-card" aria-label="Example result comparison">
          <div className="card-topline"><span>EXAMPLE REPORT</span><span className="sample-pill">SAMPLE</span></div>
          <div className="test-name">Example analyte <span>sample</span></div>
          <div className="result-row"><span>Reported value</span><strong>4.2 <small>units</small></strong></div>
          <div className="range-track" aria-hidden="true"><span className="range-marker" /></div>
          <div className="range-labels"><span>3.0</span><span>5.0</span></div>
          <div className="status-box"><span className="status-icon" aria-hidden="true">i</span><p><strong>Within the sample range</strong><br />Compared with the interval shown here. This alone doesn’t tell you what it means for your health.</p></div>
          <p className="sample-disclaimer">Illustrative only · Not a real patient result</p>
        </aside>
      </section>

      <section className="safety-strip" aria-label="Safety information">
        <span className="safety-icon" aria-hidden="true">✳</span>
        <p><strong>LabLens is an educational tool.</strong> A result outside a reference range does not automatically mean disease, and a result within range does not rule one out. Your clinician can interpret results in context.</p>
      </section>

      <section className="approach" id="how-it-works">
        <div><p className="eyebrow">THE APPROACH</p><h2>Clarity, with care.</h2></div>
        <div className="approach-copy"><p>Lab ranges vary between laboratories. LabLens is designed to compare a result with the range printed on that report, show where information came from, and help you decide what to ask next.</p><p className="coming-soon">The application is in early development. Report uploads and personalized explanations are not available yet.</p></div>
      </section>

      <footer><a className="brand footer-brand" href="#home"><span className="brand-mark" aria-hidden="true">L</span><span>LabLens</span></a><span>Built for better-informed conversations.</span></footer>
    </main>
  );
}
