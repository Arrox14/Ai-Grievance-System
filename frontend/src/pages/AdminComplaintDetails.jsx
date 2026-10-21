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
  marginBottom: "1.5rem",
};

function Detail({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <div style={{ marginBottom: "1rem" }}>
      <div style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
        {label}
      </div>
      <div style={{ color: "#f8fafc", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {value}
      </div>
    </div>
  );
}

export default function AdminComplaintDetails() {
  const { complaintId } = useParams();
  const { token } = useAuth();
  const [complaint, setComplaint] = useState(null);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [resolutionUrl, setResolutionUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const [resolutionError, setResolutionError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    const objectUrls = [];

    const loadComplaint = async () => {
      setLoading(true);
      setError("");
      setEvidenceError("");
      setResolutionError("");
      setEvidenceUrl("");
      setResolutionUrl("");
      try {
        const response = await axios.get(
          `${API_BASE}/admin/complaints/${encodeURIComponent(complaintId)}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!active) return;
        setComplaint(response.data);

        if (response.data.evidence_url) {
          try {
            const file = await axios.get(`${API_BASE}${response.data.evidence_url}`, {
              headers: { Authorization: `Bearer ${token}` },
              responseType: "blob",
            });
            const objectUrl = URL.createObjectURL(file.data);
            objectUrls.push(objectUrl);
            if (active) setEvidenceUrl(objectUrl);
          } catch (fileError) {
            if (active) {
              setEvidenceError(
                fileError.response?.data?.detail || "Evidence could not be loaded.",
              );
            }
          }
        }

        if (response.data.resolution?.attachment_url) {
          try {
            const file = await axios.get(
              `${API_BASE}${response.data.resolution.attachment_url}`,
              {
                headers: { Authorization: `Bearer ${token}` },
                responseType: "blob",
              },
            );
            const objectUrl = URL.createObjectURL(file.data);
            objectUrls.push(objectUrl);
            if (active) setResolutionUrl(objectUrl);
          } catch (fileError) {
            if (active) {
              setResolutionError(
                fileError.response?.data?.detail ||
                  "Resolution attachment could not be loaded.",
              );
            }
          }
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError.response?.data?.detail ||
              "Unable to load complaint details. Please retry.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    loadComplaint();
    return () => {
      active = false;
      objectUrls.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    };
  }, [complaintId, retry, token]);

  return (
    <main style={pageStyle}>
      <section style={{ maxWidth: "1000px", margin: "0 auto" }}>
        <Link to="/admin" style={{ display: "inline-block", color: "#38bdf8", marginBottom: "1.5rem" }}>
          Back to Admin Dashboard
        </Link>

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1" }}>Loading complaint details...</p>
        ) : error ? (
          <section role="alert" style={panelStyle}>
            <p>{error}</p>
            <button
              type="button"
              onClick={() => setRetry((current) => current + 1)}
              style={{ background: "#3b82f6", color: "white", border: 0, padding: "0.65rem 1rem", borderRadius: "0.375rem", cursor: "pointer" }}
            >
              Retry
            </button>
          </section>
        ) : complaint && (
          <>
            <section style={panelStyle}>
              <h1 style={{ margin: "0 0 1rem", fontSize: "1.75rem" }}>
                Complaint #{complaint.id}
              </h1>
              <Detail label="Category" value={complaint.category} />
              <Detail label="Priority" value={complaint.priority} />
              <Detail label="Current status" value={complaint.status} />
              <Detail
                label="Submission date"
                value={complaint.timestamp ? new Date(complaint.timestamp).toLocaleString() : null}
              />
              <Detail label="Full description" value={complaint.text} />
              {complaint.latitude != null && complaint.longitude != null && (
                <Detail label="Location" value={`${complaint.latitude}, ${complaint.longitude}`} />
              )}
              {complaint.evidence_url && (
                <div>
                  <h2 style={{ fontSize: "1.15rem" }}>Evidence</h2>
                  {evidenceError ? (
                    <p role="alert" style={{ color: "#fca5a5" }}>{evidenceError}</p>
                  ) : evidenceUrl && complaint.evidence_type?.startsWith("image/") ? (
                    <a href={evidenceUrl} target="_blank" rel="noreferrer">
                      <img
                        src={evidenceUrl}
                        alt={`Evidence for complaint ${complaint.id}`}
                        style={{ maxWidth: "100%", maxHeight: "480px", borderRadius: "0.5rem" }}
                      />
                    </a>
                  ) : evidenceUrl && complaint.evidence_type?.startsWith("video/") ? (
                    <video src={evidenceUrl} controls style={{ width: "100%", maxHeight: "480px" }} />
                  ) : evidenceUrl ? (
                    <a href={evidenceUrl} download style={{ color: "#38bdf8" }}>Download evidence</a>
                  ) : (
                    <p role="status" style={{ color: "#cbd5e1" }}>Loading evidence...</p>
                  )}
                </div>
              )}
            </section>

            <section style={panelStyle}>
              <h2 style={{ marginTop: 0 }}>Assignment</h2>
              <Detail label="Assigned officer" value={complaint.assignment?.officer_name || "Unassigned"} />
              <Detail label="Department" value={complaint.assignment?.department} />
              <Detail
                label="Assigned at"
                value={complaint.assignment?.assigned_at
                  ? new Date(complaint.assignment.assigned_at).toLocaleString()
                  : null}
              />
              <h3>Assignment history</h3>
              {complaint.assignment?.history?.length ? (
                <ol style={{ paddingLeft: "1.25rem", color: "#cbd5e1" }}>
                  {complaint.assignment.history.map((event, index) => (
                    <li key={`${event.assigned_at}-${index}`} style={{ marginBottom: "0.75rem" }}>
                      {event.previous_officer
                        ? `${event.previous_officer} reassigned to `
                        : "Assigned to "}
                      {event.officer || "Unassigned"}
                      {event.assigned_at && ` on ${new Date(event.assigned_at).toLocaleString()}`}
                      {event.assigned_by_name && ` by ${event.assigned_by_name}`}
                      {event.department && ` (${event.department})`}
                      {event.reason && <div>Reason: {event.reason}</div>}
                    </li>
                  ))}
                </ol>
              ) : (
                <p style={{ color: "#94a3b8" }}>No assignment history is recorded.</p>
              )}
            </section>

            <section style={panelStyle}>
              <h2 style={{ marginTop: 0 }}>Resolution</h2>
              {complaint.resolution ? (
                <>
                  <Detail label="Resolution date" value={complaint.resolution.date} />
                  <Detail label="Resolution remarks" value={complaint.resolution.remarks} />
                  <Detail label="Findings" value={complaint.resolution.findings} />
                  <Detail label="Submitted by" value={complaint.resolution.officer_name} />
                  <Detail
                    label="Submitted at"
                    value={complaint.resolution.submitted_at
                      ? new Date(complaint.resolution.submitted_at).toLocaleString()
                      : null}
                  />
                  <Detail label="Completed by" value={complaint.resolution.completed_by} />
                  <Detail
                    label="Completed at"
                    value={complaint.resolution.completed_at
                      ? new Date(complaint.resolution.completed_at).toLocaleString()
                      : null}
                  />
                  <Detail
                    label="Administrator review remarks"
                    value={complaint.resolution.administrator_remarks}
                  />
                  {complaint.resolution.attachment_url && (
                    resolutionError ? (
                      <p role="alert" style={{ color: "#fca5a5" }}>{resolutionError}</p>
                    ) : resolutionUrl ? (
                      <a href={resolutionUrl} download={complaint.resolution.attachment_name} style={{ color: "#38bdf8" }}>
                        Download {complaint.resolution.attachment_name || "resolution attachment"}
                      </a>
                    ) : (
                      <p role="status" style={{ color: "#cbd5e1" }}>Loading resolution attachment...</p>
                    )
                  )}
                </>
              ) : (
                <p style={{ color: "#94a3b8" }}>No resolution details are recorded.</p>
              )}
              {complaint.resolution_review && (
                <div style={{ borderTop: "1px solid #334155", paddingTop: "1rem" }}>
                  <h3>Latest resolution submission review</h3>
                  <Detail
                    label="Review outcome"
                    value={complaint.resolution_review.status.replace("_", " ")}
                  />
                  <Detail
                    label="Submitted by"
                    value={complaint.resolution_review.officer_name}
                  />
                  <Detail
                    label="Submitted at"
                    value={complaint.resolution_review.submitted_at
                      ? new Date(complaint.resolution_review.submitted_at).toLocaleString()
                      : null}
                  />
                  <Detail
                    label="Reviewed by"
                    value={complaint.resolution_review.reviewed_by}
                  />
                  <Detail
                    label="Reviewed at"
                    value={complaint.resolution_review.reviewed_at
                      ? new Date(complaint.resolution_review.reviewed_at).toLocaleString()
                      : null}
                  />
                  <Detail
                    label="Administrator review remarks"
                    value={complaint.resolution_review.administrator_remarks}
                  />
                </div>
              )}
            </section>

            <section style={panelStyle}>
              <h2 style={{ marginTop: 0 }}>Status history</h2>
              {complaint.history?.length ? (
                <ol style={{ paddingLeft: "1.25rem", color: "#cbd5e1" }}>
                  {complaint.history.map((event, index) => (
                    <li key={`${event.changed_at}-${index}`} style={{ marginBottom: "0.75rem" }}>
                      {event.previous_status
                        ? `${event.previous_status} → ${event.status}`
                        : event.status}
                      {event.changed_at && ` on ${new Date(event.changed_at).toLocaleString()}`}
                      {event.actor_name && ` by ${event.actor_name}`}
                      {event.remarks && <div>Remarks: {event.remarks}</div>}
                    </li>
                  ))}
                </ol>
              ) : (
                <p style={{ color: "#94a3b8" }}>No status transitions are recorded.</p>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
