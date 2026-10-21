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
  padding: "2rem",
};
const buttonStyle = {
  marginTop: "1rem",
  background: "#3b82f6",
  color: "white",
  border: "none",
  padding: "0.75rem 1.25rem",
  borderRadius: "0.5rem",
  cursor: "pointer",
  fontWeight: "500",
};

export default function ComplaintDetails() {
  const { complaintId } = useParams();
  const { token } = useAuth();
  const [complaint, setComplaint] = useState(null);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const [resolutionFileUrl, setResolutionFileUrl] = useState("");
  const [resolutionFileError, setResolutionFileError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    const objectUrls = [];

    const loadComplaint = async () => {
      setLoading(true);
      setError("");
      setEvidenceError("");
      setEvidenceUrl("");
      setResolutionFileUrl("");
      setResolutionFileError("");
      try {
        const response = await axios.get(
          `${API_BASE}/my-complaints/${complaintId}`,
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
            const objectUrl = URL.createObjectURL(evidence.data);
            objectUrls.push(objectUrl);
            if (active) setEvidenceUrl(objectUrl);
          } catch {
            if (active) setEvidenceError("Evidence could not be loaded.");
          }
        }
        if (response.data.resolution?.attachment_url) {
          try {
            const attachment = await axios.get(
              `${API_BASE}${response.data.resolution.attachment_url}`,
              { headers: { Authorization: `Bearer ${token}` }, responseType: "blob" }
            );
            const objectUrl = URL.createObjectURL(attachment.data);
            objectUrls.push(objectUrl);
            if (active) setResolutionFileUrl(objectUrl);
          } catch {
            if (active) setResolutionFileError("Resolution attachment could not be loaded.");
          }
        }
      } catch {
        if (active) {
          setError("Complaint not found or you do not have permission to view it.");
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
      <section style={{ maxWidth: "900px", margin: "0 auto" }}>
        <div style={{ marginBottom: "1.5rem" }}>
          <Link to="/my-complaints" style={{ color: "#38bdf8" }}>
            Back to My Complaints
          </Link>
        </div>

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1" }}>
            Loading complaint details...
          </p>
        ) : error ? (
          <div role="alert" style={panelStyle}>
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} style={buttonStyle}>
              Retry
            </button>
          </div>
        ) : complaint ? (
          <>
            <section style={{ ...panelStyle, marginBottom: "1.5rem" }}>
              <h1 style={{ margin: "0 0 1rem", fontSize: "2rem" }}>
                Complaint #{complaint.id}
              </h1>
              <Detail label="Current status" value={complaint.status} />
              <Detail label="Category" value={complaint.category} />
              <Detail
                label="Submitted"
                value={new Date(complaint.timestamp).toLocaleString()}
              />
              <Detail label="Description" value={complaint.text} />

              {complaint.latitude != null && complaint.longitude != null && (
                <Detail
                  label="Location"
                  value={`${complaint.latitude}, ${complaint.longitude}`}
                />
              )}

              {complaint.evidence_url && (
                <div style={{ marginTop: "1.25rem" }}>
                  <h2 style={sectionHeadingStyle}>Evidence</h2>
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
                    <video
                      src={evidenceUrl}
                      controls
                      style={{ width: "100%", maxHeight: "480px", borderRadius: "0.5rem" }}
                    />
                  ) : evidenceUrl ? (
                    <a href={evidenceUrl} download style={{ color: "#38bdf8" }}>
                      Download evidence
                    </a>
                  ) : (
                    <p style={{ color: "#cbd5e1" }}>Loading evidence...</p>
                  )}
                </div>
              )}
            </section>

            {complaint.resolution && (
              <section style={{ ...panelStyle, marginBottom: "1.5rem" }}>
                <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Resolution</h2>
                <Detail
                  label="Resolution date"
                  value={new Date(complaint.resolution.date).toLocaleString()}
                />
                {complaint.resolution.remarks && (
                  <Detail label="Resolution remarks" value={complaint.resolution.remarks} />
                )}
                {complaint.resolution.findings && (
                  <Detail label="Investigation findings" value={complaint.resolution.findings} />
                )}
                {complaint.resolution.officer_name && (
                  <Detail label="Submitted by" value={complaint.resolution.officer_name} />
                )}
                {complaint.resolution.submitted_at && (
                  <Detail
                    label="Submitted on"
                    value={new Date(complaint.resolution.submitted_at).toLocaleString()}
                  />
                )}
                {complaint.resolution.completed_by && (
                  <Detail label="Completed by" value={complaint.resolution.completed_by} />
                )}
                {complaint.resolution.completed_at && (
                  <Detail
                    label="Completed at"
                    value={new Date(complaint.resolution.completed_at).toLocaleString()}
                  />
                )}
                {complaint.resolution.administrator_remarks && (
                  <Detail
                    label="Administrator review remarks"
                    value={complaint.resolution.administrator_remarks}
                  />
                )}
                {complaint.resolution.attachment_name && (
                  <div style={{ marginTop: "1rem" }}>
                    <div style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                      Approved resolution attachment
                    </div>
                    {resolutionFileError ? (
                      <p role="alert" style={{ color: "#fca5a5" }}>{resolutionFileError}</p>
                    ) : resolutionFileUrl ? (
                      <a href={resolutionFileUrl} download={complaint.resolution.attachment_name} style={{ color: "#38bdf8" }}>
                        {complaint.resolution.attachment_name}
                      </a>
                    ) : (
                      <p role="status" style={{ color: "#cbd5e1" }}>Loading attachment...</p>
                    )}
                  </div>
                )}
              </section>
            )}

            <section style={panelStyle}>
              <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Status Timeline</h2>
              {complaint.history.length === 0 ? (
                <p style={{ color: "#cbd5e1" }}>
                  No status-change history was recorded for this complaint.
                </p>
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
                      {event.remarks ? (
                        <div style={{ marginTop: "0.25rem" }}>
                          Remarks: {event.remarks}
                        </div>
                      ) : (
                        <div style={{ marginTop: "0.25rem", color: "#94a3b8" }}>
                          No remarks recorded.
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </section>

            {complaint.citizen_messages?.length > 0 && (
              <section style={{ ...panelStyle, marginTop: "1.5rem" }}>
                <h2 style={{ ...sectionHeadingStyle, marginTop: 0 }}>Messages from staff</h2>
                {complaint.citizen_messages.map((message) => (
                  <article key={message.id} style={{ borderBottom: "1px solid #334155", padding: "0.75rem 0" }}>
                    <div style={{ color: "#94a3b8", fontSize: "0.875rem" }}>
                      {message.author_name} · {new Date(message.created_at).toLocaleString()}
                    </div>
                    <p style={{ color: "#f8fafc", whiteSpace: "pre-wrap", marginBottom: 0 }}>
                      {message.note}
                    </p>
                  </article>
                ))}
              </section>
            )}
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
