import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function ComplaintTracking() {
  const [complaintId, setComplaintId] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (event) => {
    event.preventDefault();
    const normalizedId = complaintId.trim();
    if (!/^\d+$/.test(normalizedId)) {
      setError("Enter a valid complaint ID.");
      return;
    }
    navigate(`/my-complaints/${normalizedId}`);
  };

  return (
    <main style={pageStyle}>
      <section style={{ ...panelStyle, maxWidth: "640px", margin: "0 auto" }}>
        <h1 style={{ marginTop: 0, fontSize: "2rem" }}>Track a Complaint</h1>
        <p style={{ color: "#cbd5e1" }}>
          Enter the ID of one of your complaints to view its details and status
          history.
        </p>
        <form onSubmit={handleSubmit}>
          <label
            htmlFor="complaint-id"
            style={{ display: "block", marginBottom: "0.5rem", color: "#cbd5e1" }}
          >
            Complaint ID
          </label>
          <input
            id="complaint-id"
            type="text"
            inputMode="numeric"
            value={complaintId}
            onChange={(event) => {
              setComplaintId(event.target.value);
              setError("");
            }}
            required
            style={inputStyle}
          />
          {error && (
            <p role="alert" style={{ color: "#fca5a5" }}>
              {error}
            </p>
          )}
          <button type="submit" style={buttonStyle}>
            Track Complaint
          </button>
        </form>
      </section>
    </main>
  );
}

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

const inputStyle = {
  boxSizing: "border-box",
  width: "100%",
  padding: "0.75rem",
  background: "#0f172a",
  border: "1px solid #475569",
  borderRadius: "0.5rem",
  color: "#f8fafc",
  fontSize: "1rem",
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
