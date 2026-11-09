"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Report = {
  id: string;
  status: string;
  media_type: string;
  byte_size: number;
  page_count: number | null;
  created_at: string;
};

type LabResult = {
  id: string;
  test_name: string;
  value_text: string;
  numeric_value: string | null;
  unit: string | null;
  reference_low: string | null;
  reference_high: string | null;
  reference_text: string | null;
  lab_flag: string | null;
  page_number: number | null;
  review_status: string;
  range_status: string | null;
};

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "Waiting for secure processing",
    processing_failed: "Processing needs attention",
    awaiting_review: "Ready for your review",
    deleting: "Deletion in progress",
    failed: "Processing failed",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export default function ReportDashboard() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const response = await fetch("/api/proxy/reports", { cache: "no-store" });
    if (response.status === 401) throw new Error("Your sign-in expired. Please sign in again.");
    if (!response.ok) throw new Error(await readError(response));
    setReports(await response.json());
    setLoading(false);
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Reports could not be loaded.");
      setLoading(false);
    }), 0);
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 5000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
    };
  }, [refresh]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setError("");
    try {
      const formData = new FormData(formElement);
      const response = await fetch("/api/proxy/reports", { method: "POST", body: formData });
      if (!response.ok) throw new Error(await readError(response));
      formElement.reset();
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteReport(reportId: string) {
    if (!window.confirm("Delete this report and its associated extracted results?")) return;
    setError("");
    const response = await fetch(`/api/proxy/reports/${reportId}`, { method: "DELETE" });
    if (!response.ok) setError(await readError(response));
    await refresh();
  }

  async function retryReport(reportId: string) {
    const response = await fetch(`/api/proxy/reports/${reportId}/retry`, { method: "POST" });
    if (!response.ok) setError(await readError(response));
    await refresh();
  }

  async function downloadReport(reportId: string) {
    const response = await fetch(`/api/proxy/reports/${reportId}/document`, { cache: "no-store" });
    if (!response.ok) {
      setError(await readError(response));
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `LabLens-report-${reportId}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="report-workspace" aria-label="Report management">
      <form className="upload-panel" onSubmit={upload}>
        <div>
          <p className="eyebrow">ADD A REPORT</p>
          <h2>Start with the original document.</h2>
          <p>PDF, PNG, or JPEG · up to 10 MB. The original is stored privately and can be deleted here.</p>
        </div>
        <label className="file-picker">Choose a report<input name="file" type="file" accept="application/pdf,image/png,image/jpeg" required /></label>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? "Uploading…" : "Upload securely"}</button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="report-list-heading"><h2>Your reports</h2><span>{reports.length}</span></div>
      {loading ? <p className="empty-state">Loading your private reports…</p> : reports.length === 0 ? (
        <p className="empty-state">No reports yet. Upload a report when you’re ready.</p>
      ) : (
        <div className="report-list">
          {reports.map((report) => (
            <article className="report-item" key={report.id}>
              <div className="report-heading">
                <div><span className="report-type">{report.media_type === "application/pdf" ? "PDF report" : "Image report"}</span><p>{statusLabel(report.status)}</p></div>
                <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleDateString()}</time>
              </div>
              <div className="report-actions">
                <button className="small-button" type="button" onClick={() => void downloadReport(report.id)}>Open original</button>
                {report.status === "processing_failed" && <button className="small-button" type="button" onClick={() => void retryReport(report.id)}>Retry processing</button>}
                <button className="small-button danger-button" type="button" onClick={() => void deleteReport(report.id)}>Delete report</button>
              </div>
              {report.status === "awaiting_review" && <ReviewPanel report={report} onChange={() => void refresh()} />}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ReviewPanel({ report, onChange }: { report: Report; onChange: () => void }) {
  const [results, setResults] = useState<LabResult[]>([]);
  const [editing, setEditing] = useState<LabResult | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const response = await fetch(`/api/proxy/reports/${report.id}/results`, { cache: "no-store" });
    if (!response.ok) throw new Error(await readError(response));
    setResults(await response.json());
  }, [report.id]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void refresh().catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Results could not be loaded."),
      );
    }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [refresh]);

  async function saveResult(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setError("");
    const form = new FormData(formElement);
    const optionalNumber = (key: string) => String(form.get(key) ?? "").trim() || null;
    const payload = {
      test_name: String(form.get("test_name") ?? "").trim(),
      value_text: String(form.get("value_text") ?? "").trim(),
      numeric_value: optionalNumber("numeric_value"),
      unit: optionalNumber("unit"),
      reference_low: optionalNumber("reference_low"),
      reference_high: optionalNumber("reference_high"),
      reference_text: optionalNumber("reference_text"),
      lab_flag: optionalNumber("lab_flag"),
      page_number: optionalNumber("page_number"),
    };
    const endpoint = editing
      ? `/api/proxy/reports/${report.id}/results/${editing.id}`
      : `/api/proxy/reports/${report.id}/results`;
    const response = await fetch(endpoint, {
      method: editing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      setError(await readError(response));
      return;
    }
    setEditing(null);
    formElement.reset();
    await refresh();
    onChange();
  }

  async function confirmResult(resultId: string) {
    const response = await fetch(`/api/proxy/reports/${report.id}/results/${resultId}/confirm`, { method: "POST" });
    if (!response.ok) {
      setError(await readError(response));
      return;
    }
    await refresh();
  }

  return (
    <section className="review-panel" aria-label="Review extracted results">
      <p className="eyebrow">REVIEW BEFORE COMPARISON</p>
      <p className="review-note">This starter does not extract result rows automatically. Enter values exactly as printed, and check the original report before confirming each row.</p>
      {report.page_count !== null && <p className="page-count">Document pages: {report.page_count}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {results.map((result) => (
        <div className="result-review" key={result.id}>
          <div><strong>{result.test_name}</strong><span>{result.value_text}{result.unit ? ` ${result.unit}` : ""}</span><small>{result.review_status === "confirmed" ? `Compared: ${result.range_status?.replaceAll("_", " ")}` : "Needs your review"}</small></div>
          <div className="result-review-actions">
            {result.review_status !== "confirmed" && <button className="small-button" type="button" onClick={() => setEditing(result)}>Correct</button>}
            {result.review_status !== "confirmed" && <button className="small-button" type="button" onClick={() => void confirmResult(result.id)}>Confirm against report</button>}
          </div>
        </div>
      ))}
      <form className="result-form" onSubmit={saveResult} key={editing?.id ?? "new-result"}>
        <h3>{editing ? "Correct a result" : "Add a result for review"}</h3>
        <div className="result-fields">
          <label>Test name<input name="test_name" required defaultValue={editing?.test_name ?? ""} maxLength={256} /></label>
          <label>Reported value<input name="value_text" required defaultValue={editing?.value_text ?? ""} maxLength={256} /></label>
          <label>Numeric value<input name="numeric_value" inputMode="decimal" defaultValue={editing?.numeric_value ?? ""} /></label>
          <label>Unit<input name="unit" defaultValue={editing?.unit ?? ""} maxLength={64} /></label>
          <label>Range lower bound<input name="reference_low" inputMode="decimal" defaultValue={editing?.reference_low ?? ""} /></label>
          <label>Range upper bound<input name="reference_high" inputMode="decimal" defaultValue={editing?.reference_high ?? ""} /></label>
          <label>Range as printed<input name="reference_text" defaultValue={editing?.reference_text ?? ""} maxLength={256} /></label>
          <label>Report page<input name="page_number" inputMode="numeric" defaultValue={editing?.page_number ?? ""} /></label>
          <label>Lab flag<input name="lab_flag" defaultValue={editing?.lab_flag ?? ""} maxLength={64} /></label>
        </div>
        <button className="small-button" type="submit">{editing ? "Save correction" : "Add for review"}</button>
        {editing && <button className="text-button cancel-edit" type="button" onClick={() => setEditing(null)}>Cancel</button>}
      </form>
    </section>
  );
}
