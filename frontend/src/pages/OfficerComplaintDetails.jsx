import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const pageStyle = {
  minHeight: "calc(100vh - 80px)",
  background: "#0f172a",
  padding: "2rem",
  color: "#f8fafc",
};
const panelStyle = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "0.75rem",
  padding: "1.5rem",
};

export default function OfficerComplaintDetails() {
  const { complaintId } = useParams();
  const { token } = useAuth();
  const [complaint, setComplaint] = useState(null);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [error, setError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [noteText, setNoteText] = useState("");
  const [noteType, setNoteType] = useState("internal");
  const [savingNote, setSavingNote] = useState(false);
  const [noteError, setNoteError] = useState("");
  const [statusRemarks, setStatusRemarks] = useState("");
  const [resolutionDate, setResolutionDate] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [resolutionFindings, setResolutionFindings] = useState("");
  const [resolutionRemarks, setResolutionRemarks] = useState("");
  const [resolutionFile, setResolutionFile] = useState(null);
  const [submittingResolution, setSubmittingResolution] = useState(false);
  const [resolutionError, setResolutionError] = useState("");
  const nextStatus = "In Progress";

  const addNote = async (event) => {
    event.preventDefault();
    setSavingNote(true);
    setNoteError("");
    try {
      await axios.post(
        `${API_BASE}/officer/complaints/${complaintId}/notes`,
        { note_type: noteType, note: noteText },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNoteText("");
      setRetry((value) => value + 1);
    } catch (requestError) {
      setNoteError(requestError.response?.data?.detail || "Unable to save investigation note.");
    } finally {
      setSavingNote(false);
    }
  };

  const updateStatus = async (event) => {
    event.preventDefault();
    setSavingStatus(true);
    setStatusError("");
    try {
      await axios.put(
        `${API_BASE}/officer/complaints/${complaintId}/status`,
        {
          status: nextStatus,
          remarks: statusRemarks,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStatusRemarks("");
      setRetry((value) => value + 1);
    } catch (requestError) {
      setStatusError(requestError.response?.data?.detail || "Unable to update complaint status.");
    } finally {
      setSavingStatus(false);
    }
  };

  const submitResolution = async (event) => {
    event.preventDefault();
    setSubmittingResolution(true);
    setResolutionError("");
    if (!resolutionFile || resolutionFile.size > 10 * 1024 * 1024) {
      setResolutionError("Choose an attachment no larger than 10 MB.");
      setSubmittingResolution(false);
      return;
    }
    const formData = new FormData();
    formData.append("findings", resolutionFindings);
    formData.append("remarks", resolutionRemarks);
    formData.append("resolution_date", resolutionDate);
    formData.append("file", resolutionFile);
    try {
      await axios.post(
        `${API_BASE}/officer/complaints/${complaintId}/resolution`,
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setResolutionFindings("");
      setResolutionRemarks("");
      setResolutionDate("");
      setResolutionFile(null);
      setRetry((value) => value + 1);
    } catch (requestError) {
      setResolutionError(
        requestError.response?.data?.detail || "Unable to submit resolution for review."
      );
    } finally {
      setSubmittingResolution(false);
    }
  };

  const openResolutionAttachment = async (submission) => {
    try {
      const response = await axios.get(`${API_BASE}${submission.attachment_url}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      setResolutionError("Unable to open the resolution attachment.");
    }
  };

  useEffect(() => {
    let active = true;
    let objectUrl = "";

    const loadComplaint = async () => {
      setLoading(true);
      setError("");
      setEvidenceError("");
      setEvidenceUrl("");
      setComplaint(null);
      try {
        const response = await axios.get(
          `${API_BASE}/officer/complaints/${complaintId}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!active) return;
        setComplaint(response.data);

        if (response.data.evidence_url) {
          try {
            const evidence = await axios.get(
              `${API_BASE}${response.data.evidence_url}`,
              {
                headers: { Authorization: `Bearer ${token}` },
                responseType: "blob",
              }
            );
            objectUrl = URL.createObjectURL(evidence.data);
            if (active) setEvidenceUrl(objectUrl);
          } catch {
            if (active) setEvidenceError("Evidence is unavailable or could not be loaded.");
          }
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError.response?.status === 404
              ? "Complaint not found or it is not assigned to your account."
              : "Unable to load this complaint. Please try again."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    loadComplaint();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [complaintId, retry, token]);

  return (
    <main style={pageStyle}>
      <section style={{ maxWidth: "950px", margin: "0 auto" }}>
        <Link to="/officer" style={{ color: "#38bdf8" }}>
          Back to Officer Dashboard
        </Link>

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1", marginTop: "1.5rem" }}>
            Loading complaint investigation...
          </p>
        ) : error ? (
          <div role="alert" style={{ ...panelStyle, marginTop: "1.5rem" }}>
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} style={buttonStyle}>
              Retry
            </button>
          </div>
        ) : complaint ? (
          <>
            <section style={{ ...panelStyle, marginTop: "1.5rem", marginBottom: "1.5rem" }}>
              <h1 style={{ marginTop: 0, fontSize: "2rem" }}>
                Complaint #{complaint.id}
              </h1>
              <Detail label="Category" value={complaint.category} />
              <Detail label="Priority" value={complaint.priority} />
              <Detail label="Current status" value={complaint.status} />
              <Detail label="Assignment" value={`Assigned to ${complaint.assigned_officer || "you"}`} />
              <Detail
                label="Assignment date"
                value={complaint.assigned_at
                  ? new Date(complaint.assigned_at).toLocaleString()
                  : "Not recorded"}
              />
              <Detail label="Submission date" value={new Date(complaint.timestamp).toLocaleString()} />
              <Detail label="Description" value={complaint.text} />
              {complaint.latitude != null && complaint.longitude != null && (
                <Detail label="Location" value={`${complaint.latitude}, ${complaint.longitude}`} />
              )}

              {complaint.evidence_url && (
                <div style={{ marginTop: "1.5rem" }}>
                  <h2 style={sectionHeadingStyle}>Submitted Evidence</h2>
                  {evidenceError ? (
                    <p role="alert" style={{ color: "#fca5a5" }}>{evidenceError}</p>
                  ) : evidenceUrl && complaint.evidence_type?.startsWith("image/") ? (
                    <a href={evidenceUrl} target="_blank" rel="noreferrer">
                      <img
                        src={evidenceUrl}
                        alt={`Evidence for complaint ${complaint.id}`}
                        style={{ maxWidth: "100%", maxHeight: "520px", borderRadius: "0.5rem" }}
                      />
                    </a>
                  ) : evidenceUrl && complaint.evidence_type?.startsWith("video/") ? (
                    <video
                      src={evidenceUrl}
                      controls
                      style={{ width: "100%", maxHeight: "520px", borderRadius: "0.5rem" }}
                    />
                  ) : evidenceUrl ? (
                    <a href={evidenceUrl} download style={{ color: "#38bdf8" }}>
                      Download submitted evidence
                    </a>
                  ) : (
                    <p style={{ color: "#cbd5e1" }}>Loading evidence...</p>
                  )}
                </div>
              )}
            </section>

            <section style={panelStyle}>
              <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Investigation Notes</h2>
              <form onSubmit={addNote} style={{ display: "grid", gap: "0.75rem", marginBottom: "1.5rem" }}>
                <label>
                  Note visibility
                  <select value={noteType} onChange={(event) => setNoteType(event.target.value)} style={inputStyle}>
                    <option value="internal">Internal (staff only)</option>
                    <option value="citizen_visible">Visible to complaint owner</option>
                  </select>
                </label>
                <label>
                  Note
                  <textarea
                    value={noteText}
                    onChange={(event) => setNoteText(event.target.value)}
                    maxLength={5000}
                    required
                    rows={4}
                    style={inputStyle}
                  />
                </label>
                {noteError && <p role="alert" style={{ color: "#fca5a5" }}>{noteError}</p>}
                <button type="submit" disabled={savingNote} style={buttonStyle}>
                  {savingNote ? "Saving..." : "Add note"}
                </button>
              </form>
              {complaint.notes.length === 0 ? (
                <p style={{ color: "#cbd5e1" }}>No investigation notes yet.</p>
              ) : (
                <ol style={{ paddingLeft: "1.5rem" }}>
                  {complaint.notes.map((note) => (
                    <li key={note.id} style={{ marginBottom: "1rem", color: "#cbd5e1" }}>
                      <strong style={{ color: "#f8fafc" }}>
                        {note.note_type === "internal" ? "Internal note" : "Message to citizen"}
                      </strong>
                      <div>{new Date(note.created_at).toLocaleString()} · {note.author_name}</div>
                      <p style={{ whiteSpace: "pre-wrap" }}>{note.note}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section style={{ ...panelStyle, marginTop: "1.5rem" }}>
              <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Update Status</h2>
              {complaint.status === "Pending" ? (
                <form onSubmit={updateStatus} style={{ display: "grid", gap: "0.75rem" }}>
                  <p style={{ color: "#cbd5e1" }}>
                    Move this assigned complaint into investigation before submitting resolution.
                  </p>
                  <label>
                    Investigation update
                    <textarea
                      value={statusRemarks}
                      onChange={(event) => setStatusRemarks(event.target.value)}
                      maxLength={2000}
                      rows={3}
                      style={inputStyle}
                    />
                  </label>
                  {statusError && <p role="alert" style={{ color: "#fca5a5" }}>{statusError}</p>}
                  <button type="submit" disabled={savingStatus} style={buttonStyle}>
                    {savingStatus ? "Updating..." : "Update status"}
                  </button>
                </form>
              ) : complaint.status === "In Progress" && complaint.resolution_submission?.review_status !== "pending_review" ? (
                <form onSubmit={submitResolution} style={{ display: "grid", gap: "0.75rem" }}>
                  <label>
                    Investigation findings
                    <textarea
                      value={resolutionFindings}
                      onChange={(event) => setResolutionFindings(event.target.value)}
                      maxLength={10000}
                      required
                      rows={4}
                      style={inputStyle}
                    />
                  </label>
                  <label>
                    Resolution remarks
                    <textarea
                      value={resolutionRemarks}
                      onChange={(event) => setResolutionRemarks(event.target.value)}
                      maxLength={5000}
                      required
                      rows={3}
                      style={inputStyle}
                    />
                  </label>
                  <label>
                    Resolution date
                    <input
                      type="date"
                      value={resolutionDate}
                      onChange={(event) => setResolutionDate(event.target.value)}
                      required
                      style={inputStyle}
                    />
                  </label>
                  <label>
                    Resolution photograph or document (JPEG, PNG, WebP, PDF, DOCX; max 10 MB)
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.pdf,.docx,image/jpeg,image/png,image/webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={(event) => setResolutionFile(event.target.files?.[0] || null)}
                      required
                      style={{ ...inputStyle, padding: "0.5rem" }}
                    />
                  </label>
                  {resolutionError && <p role="alert" style={{ color: "#fca5a5" }}>{resolutionError}</p>}
                  <button type="submit" disabled={submittingResolution} style={buttonStyle}>
                    {submittingResolution ? "Submitting..." : "Submit resolution for Admin review"}
                  </button>
                </form>
              ) : complaint.status === "In Progress" ? (
                <p role="status" style={{ color: "#cbd5e1" }}>
                  Resolution submission is awaiting administrator review.
                </p>
              ) : (
                <p style={{ color: "#cbd5e1" }}>This complaint is resolved.</p>
              )}
              {complaint.resolution_submission && (
                <div style={{ marginTop: "1rem", borderTop: "1px solid #334155", paddingTop: "1rem" }}>
                  <Detail
                    label="Latest resolution submission"
                    value={`${complaint.resolution_submission.review_status.replace("_", " ")} · ${new Date(complaint.resolution_submission.submitted_at).toLocaleString()}`}
                  />
                  {complaint.resolution_submission.review_remarks && (
                    <Detail label="Admin review remarks" value={complaint.resolution_submission.review_remarks} />
                  )}
                  {complaint.resolution_submission.reviewed_by_name && (
                    <Detail label="Reviewed by" value={complaint.resolution_submission.reviewed_by_name} />
                  )}
                  {complaint.resolution_submission.reviewed_at && (
                    <Detail
                      label="Reviewed at"
                      value={new Date(complaint.resolution_submission.reviewed_at).toLocaleString()}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => openResolutionAttachment(complaint.resolution_submission)}
                    style={{ ...buttonStyle, marginTop: "0.75rem" }}
                  >
                    View {complaint.resolution_submission.attachment_name}
                  </button>
                </div>
              )}
            </section>

            <section style={{ ...panelStyle, marginTop: "1.5rem" }}>
              <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Status History</h2>
              {complaint.history.length === 0 ? (
                <p style={{ color: "#cbd5e1" }}>No status history is available.</p>
              ) : (
                <ol style={{ margin: 0, paddingLeft: "1.5rem" }}>
                  {complaint.history.map((event, index) => (
                    <li
                      key={`${event.changed_at}-${index}`}
                      style={{ padding: "0 0 1.25rem 0.5rem", color: "#cbd5e1" }}
                    >
                      <strong style={{ color: "#f8fafc" }}>{event.status}</strong>
                      {event.previous_status && <div>Changed from {event.previous_status}</div>}
                      <div>{new Date(event.changed_at).toLocaleString()}</div>
                      <div>Updated by {event.actor_name}</div>
                      {event.remarks && <div>Remarks: {event.remarks}</div>}
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}

function Detail({ label, value }) {
  return (
    <div style={{ marginTop: "1rem" }}>
      <div style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
        {label}
      </div>
      <div style={{ color: "#f8fafc", whiteSpace: "pre-wrap" }}>{value}</div>
    </div>
  );
}

const sectionHeadingStyle = {
  color: "#f8fafc",
  fontSize: "1.25rem",
  marginBottom: "1rem",
};

const buttonStyle = {
  background: "#3b82f6",
  color: "white",
  border: "none",
  padding: "0.6rem 1rem",
  borderRadius: "0.375rem",
  cursor: "pointer",
};

const inputStyle = {
  display: "block",
  width: "100%",
  marginTop: "0.35rem",
  padding: "0.65rem",
  color: "#f8fafc",
  background: "#0f172a",
  border: "1px solid #475569",
  borderRadius: "0.375rem",
};
