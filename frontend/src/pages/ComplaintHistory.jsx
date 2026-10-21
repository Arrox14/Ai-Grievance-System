import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const PAGE_SIZE = 10;
const STATUSES = ["Pending", "In Progress", "Resolved"];

export default function ComplaintHistory() {
  const { token } = useAuth();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;

    const loadComplaints = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await axios.get(`${API_BASE}/my-complaints`, {
          headers: { Authorization: `Bearer ${token}` },
          params: {
            limit: PAGE_SIZE,
            offset: page * PAGE_SIZE,
            ...(status ? { status } : {}),
          },
        });
        if (active) {
          setItems(response.data.items);
          setTotal(response.data.total);
        }
      } catch {
        if (active) {
          setError("Unable to load your complaint history. Please try again.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadComplaints();
    return () => {
      active = false;
    };
  }, [page, retry, status, token]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main
      style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
        color: "#f8fafc",
      }}
    >
      <section style={{ maxWidth: "1000px", margin: "0 auto" }}>
        <h1 style={{ fontSize: "2rem", margin: "0 0 1.5rem" }}>
          My Complaints
        </h1>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          <label style={{ color: "#cbd5e1" }}>
            Filter by status{" "}
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(0);
              }}
              style={{
                marginLeft: "0.5rem",
                padding: "0.5rem",
                background: "#1e293b",
                border: "1px solid #475569",
                borderRadius: "0.375rem",
                color: "#f8fafc",
              }}
            >
              <option value="">All statuses</option>
              {STATUSES.map((itemStatus) => (
                <option key={itemStatus} value={itemStatus}>
                  {itemStatus}
                </option>
              ))}
            </select>
          </label>
          {!loading && !error && (
            <span style={{ color: "#94a3b8" }}>
              {total} {total === 1 ? "complaint" : "complaints"}
            </span>
          )}
        </div>

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1" }}>
            Loading your complaint history...
          </p>
        ) : error ? (
          <div
            role="alert"
            style={{
              padding: "1rem",
              background: "#1e293b",
              border: "1px solid #ef4444",
              borderRadius: "0.5rem",
            }}
          >
            <p style={{ marginTop: 0 }}>{error}</p>
            <button
              type="button"
              onClick={() => setRetry((value) => value + 1)}
              style={{
                background: "#3b82f6",
                color: "white",
                border: "none",
                padding: "0.6rem 1rem",
                borderRadius: "0.375rem",
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <div
            style={{
              padding: "2rem",
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "0.75rem",
              color: "#cbd5e1",
              textAlign: "center",
            }}
          >
            No complaints found{status ? ` with status "${status}"` : ""}.
          </div>
        ) : (
          <>
            <div
              style={{
                overflowX: "auto",
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "0.75rem",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ color: "#cbd5e1", textAlign: "left" }}>
                    {["Complaint ID", "Submission Date", "Category", "Status"].map(
                      (heading) => (
                        <th
                          key={heading}
                          scope="col"
                          style={{
                            padding: "1rem",
                            borderBottom: "1px solid #475569",
                          }}
                        >
                          {heading}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td style={{ padding: "1rem", borderBottom: "1px solid #334155" }}>
                        <Link
                          to={`/my-complaints/${item.id}`}
                          style={{ color: "#38bdf8" }}
                        >
                          #{item.id}
                        </Link>
                      </td>
                      <td style={{ padding: "1rem", borderBottom: "1px solid #334155" }}>
                        {new Date(item.timestamp).toLocaleString()}
                      </td>
                      <td style={{ padding: "1rem", borderBottom: "1px solid #334155" }}>
                        {item.category}
                      </td>
                      <td style={{ padding: "1rem", borderBottom: "1px solid #334155" }}>
                        {item.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: "1rem",
                color: "#cbd5e1",
              }}
            >
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((value) => value - 1)}
                style={paginationButtonStyle(page === 0)}
              >
                Previous
              </button>
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((value) => value + 1)}
                style={paginationButtonStyle(page + 1 >= totalPages)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function paginationButtonStyle(disabled) {
  return {
    background: disabled ? "#334155" : "#3b82f6",
    color: "white",
    border: "none",
    padding: "0.6rem 1rem",
    borderRadius: "0.375rem",
    cursor: disabled ? "not-allowed" : "pointer",
  };
}
