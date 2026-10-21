import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function formatError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg || "Invalid input").join(" ");
  }
  if (!error.response) {
    if (!error.isAxiosError && error.message) return error.message;
    return "Cannot reach the authentication server. Start the FastAPI backend and try again.";
  }
  if (error.message && error.message !== "Request failed with status code 401") {
    return error.message;
  }
  return "Login failed. Please try again.";
}

function dashboardForRole(role) {
  return role === "admin" ? "/admin" : role === "officer" ? "/officer" : "/account";
}

function destinationForRole(role, requestedPath) {
  const allowedPrefixes = {
    admin: ["/admin"],
    officer: ["/officer", "/officer-dashboard"],
    citizen: ["/account", "/upload", "/my-complaints", "/track", "/notifications"],
  };
  const allowedPath = allowedPrefixes[role]?.some(
    (prefix) => requestedPath === prefix || requestedPath?.startsWith(`${prefix}/`),
  );
  return allowedPath ? requestedPath : dashboardForRole(role);
}

export default function Login() {
  const { isAuthenticated, isAdmin, isOfficer, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const dedicatedRole = location.pathname === "/officer-login"
    ? "officer"
    : location.pathname === "/admin-login"
      ? "admin"
      : null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginRole, setLoginRole] = useState("citizen");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const activeRole = dedicatedRole || loginRole;
  const roleTitle = activeRole === "admin"
    ? "Administrator"
    : activeRole === "officer"
      ? "Officer"
      : "Citizen";

  if (isAuthenticated) {
    const role = isAdmin ? "admin" : isOfficer ? "officer" : "citizen";
    return (
      <Navigate
        to={destinationForRole(role, location.state?.from)}
        replace
      />
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Email and password are required");
      return;
    }

    setSubmitting(true);
    try {
      const user = await login(email.trim(), password, activeRole);
      navigate(
        destinationForRole(user.role, location.state?.from),
        { replace: true }
      );
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmitting(false);
    }
  };

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
          {roleTitle} Login
        </h1>

        <form
          onSubmit={handleSubmit}
          style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
          }}
        >
          {!dedicatedRole && (
            <div
              role="group"
              aria-label="Choose account type"
              style={{
                display: "flex",
                gap: "0.75rem",
                marginBottom: "1.5rem",
              }}
            >
              {[
                { value: "citizen", label: "Citizen Login" },
                { value: "admin", label: "Administrator Login" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={loginRole === option.value}
                  onClick={() => {
                    setLoginRole(option.value);
                    setError("");
                  }}
                  style={{
                    flex: 1,
                    background: loginRole === option.value ? "#3b82f6" : "#0f172a",
                    color: "#f8fafc",
                    border: "1px solid #475569",
                    padding: "0.75rem",
                    borderRadius: "0.5rem",
                    cursor: "pointer",
                    fontWeight: "600",
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}

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
          {location.state?.sessionExpired && !error && (
            <div
              role="status"
              style={{
                background: "#0f172a",
                border: "1px solid #f59e0b",
                color: "#f8fafc",
                borderRadius: "0.5rem",
                padding: "0.75rem",
                marginBottom: "1.5rem",
              }}
            >
              Your session expired. Please sign in again.
            </div>
          )}

          <div style={{ marginBottom: "1.5rem" }}>
            <label
              style={{
                display: "block",
                color: "#f8fafc",
                fontWeight: "500",
                marginBottom: "0.5rem",
              }}
            >
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "0.5rem",
                color: "#f8fafc",
                fontSize: "1rem",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <label
              style={{
                display: "block",
                color: "#f8fafc",
                fontWeight: "500",
                marginBottom: "0.5rem",
              }}
            >
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "0.5rem",
                color: "#f8fafc",
                fontSize: "1rem",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            style={{
              width: "100%",
              background: submitting ? "#64748b" : "#3b82f6",
              color: "white",
              border: "none",
              padding: "1rem",
              borderRadius: "0.5rem",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting ? "Signing in..." : "Login"}
          </button>

          {!dedicatedRole && loginRole === "citizen" && (
            <p style={{ color: "#cbd5e1", marginTop: "1.5rem", textAlign: "center" }}>
              New citizen?{" "}
              <Link to="/register" style={{ color: "#3b82f6" }}>
                Create an account
              </Link>
            </p>
          )}
          {dedicatedRole && (
            <p style={{ color: "#cbd5e1", marginTop: "1.5rem", textAlign: "center" }}>
              <Link to="/login" style={{ color: "#38bdf8" }}>
                Back to User Login
              </Link>
            </p>
          )}
          {activeRole === "admin" && (
            <p style={{ color: "#cbd5e1", marginTop: "0.75rem", textAlign: "center" }}>
              <Link to="/officer-login" style={{ color: "#38bdf8" }}>
                Officer Login
              </Link>
            </p>
          )}
          {activeRole === "admin" && (
            <p style={{ color: "#94a3b8", marginTop: "0.75rem", textAlign: "center" }}>
              First administrator?{" "}
              <Link to="/admin-setup" style={{ color: "#38bdf8" }}>
                Set up administrator access
              </Link>
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
