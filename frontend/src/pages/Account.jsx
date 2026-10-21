import { useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";

export default function Account() {
  const { token, user, logout } = useAuth();
  const [profile, setProfile] = useState(user);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;

    axios
      .get(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((response) => {
        setProfile(response.data);
      })
      .catch(() => {
        setError("Unable to load your account details.");
      });
  }, [token]);

  const details = profile || user;

  return (
    <div
      style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: "800px", margin: "0 auto" }}>
        <h1
          style={{
            color: "#f8fafc",
            fontSize: "2rem",
            fontWeight: "bold",
            marginBottom: "2rem",
            textAlign: "center",
          }}
        >
          My Account
        </h1>

        <div
          style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
          }}
        >
          {error && (
            <div
              style={{
                background: "#0f172a",
                border: "1px solid #ef4444",
                color: "#f8fafc",
                borderRadius: "0.5rem",
                padding: "0.75rem",
                marginBottom: "1.5rem",
              }}
            >
              {error}
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1rem",
            }}
          >
            <div
              style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569",
              }}
            >
              <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                Name
              </div>
              <div style={{ color: "#f8fafc", fontWeight: "600" }}>{details?.name}</div>
            </div>
            <div
              style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569",
              }}
            >
              <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                Email
              </div>
              <div style={{ color: "#f8fafc", fontWeight: "600" }}>{details?.email}</div>
            </div>
            <div
              style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569",
              }}
            >
              <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                Role
              </div>
              <div style={{ color: "#f8fafc", fontWeight: "600", textTransform: "capitalize" }}>
                {details?.role}
              </div>
            </div>
          </div>

          <p style={{ color: "#94a3b8", marginTop: "1.5rem", fontSize: "0.875rem" }}>
            This page is private. Only you can see your account details.
          </p>

          <button
            type="button"
            onClick={logout}
            style={{
              marginTop: "1.5rem",
              background: "#ef4444",
              color: "white",
              border: "none",
              padding: "0.75rem 1.5rem",
              borderRadius: "0.5rem",
              cursor: "pointer",
              fontWeight: "500",
            }}
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}
