import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const STATUSES = ["Pending", "In Progress", "Resolved"];

export default function OfficerDashboard() {
  const { token } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    const loadComplaints = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await axios.get(`${API_BASE}/officer/complaints`, {
          headers: { Authorization: `Bearer ${token}` },
          params: { ...(search.trim() ? { search: search.trim() } : {}), ...(status ? { status } : {}) },
        });
        if (active) setComplaints(response.data);
      } catch {
        if (active) setError("Unable to load assigned complaints. Please try again.");
      } finally {
        if (active) setLoading(false);
      }
    };
    loadComplaints();
    return () => {
      active = false;
    };
  }, [retry, search, status, token]);

  return (
    <main
      style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
        color: "#f8fafc",
      }}
    >
      <section style={{ maxWidth: "1100px", margin: "0 auto" }}>
        <h1 style={{ fontSize: "2rem", margin: "0 0 1.5rem" }}>
          Officer Dashboard
        </h1>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          <label style={{ color: "#cbd5e1" }}>
            Search by complaint ID, category or priority
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search assigned complaints"
              style={fieldStyle}
            />
          </label>
          <label style={{ color: "#cbd5e1" }}>
            Filter by status
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              style={fieldStyle}
            >
              <option value="">All statuses</option>
              {STATUSES.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1" }}>Loading assigned complaints...</p>
        ) : error ? (
          <div role="alert" style={panelStyle}>
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} style={buttonStyle}>
              Retry
            </button>
          </div>
        ) : complaints.length === 0 ? (
          <div style={{ ...panelStyle, textAlign: "center" }}>
            No assigned complaints match your search or status filter.
          </div>
        ) : (
          <div style={{ overflowX: "auto", ...panelStyle }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "#cbd5e1", textAlign: "left" }}>
                  {["Complaint ID", "Description", "Category", "Priority", "Submission Date", "Status"].map((heading) => (
                    <th key={heading} scope="col" style={cellHeaderStyle}>{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {complaints.map((complaint) => (
                  <tr key={complaint.id}>
                    <td style={cellStyle}>
                      <Link
                        to={`/officer/complaints/${complaint.id}`}
                        style={{ color: "#38bdf8" }}
                      >
                        #{complaint.id}
                      </Link>
                    </td>
                    <td style={{ ...cellStyle, maxWidth: "360px", whiteSpace: "pre-wrap" }}>
                      {complaint.description}
                    </td>
                    <td style={cellStyle}>{complaint.category}</td>
                    <td style={cellStyle}>{complaint.priority}</td>
                    <td style={cellStyle}>
                      {complaint.submitted_at
                        ? new Date(complaint.submitted_at).toLocaleString()
                        : "Not recorded"}
                    </td>
                    <td style={cellStyle}>{complaint.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

const panelStyle = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "0.75rem",
  padding: "1.5rem",
  color: "#cbd5e1",
};

const fieldStyle = {
  display: "block",
  boxSizing: "border-box",
  width: "100%",
  marginTop: "0.5rem",
  padding: "0.65rem",
  background: "#1e293b",
  border: "1px solid #475569",
  borderRadius: "0.375rem",
  color: "#f8fafc",
};

const cellHeaderStyle = {
  padding: "0.9rem",
  borderBottom: "1px solid #475569",
  whiteSpace: "nowrap",
};

const cellStyle = {
  padding: "0.9rem",
  borderBottom: "1px solid #334155",
};

const buttonStyle = {
  background: "#3b82f6",
  color: "white",
  border: "none",
  padding: "0.6rem 1rem",
  borderRadius: "0.375rem",
  cursor: "pointer",
};
