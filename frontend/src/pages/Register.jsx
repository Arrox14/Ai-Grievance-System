import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function formatError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg || "Invalid input").join(" ");
  }
  if (!error.response) {
    return "Cannot reach the authentication server. Start the FastAPI backend and try again.";
  }
  if (error.message) return error.message;
  return "Registration failed. Please try again.";
}

export default function Register() {
  const { isAuthenticated, register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/account" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (name.trim().length < 2) {
      setError("Name must be at least 2 characters");
      return;
    }
    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    try {
      await register(name.trim(), email.trim(), password);
      navigate("/account", { replace: true });
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
          Citizen Registration
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

          <div style={{ marginBottom: "1.5rem" }}>
            <label
              style={{
                display: "block",
                color: "#f8fafc",
                fontWeight: "500",
                marginBottom: "0.5rem",
              }}
            >
              Full Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
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
              minLength={8}
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
              Confirm Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
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
            {submitting ? "Creating account..." : "Register"}
          </button>

          <p style={{ color: "#cbd5e1", marginTop: "1.5rem", textAlign: "center" }}>
            Already registered?{" "}
            <Link to="/login" style={{ color: "#3b82f6" }}>
              Login
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
