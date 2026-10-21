import { useState } from "react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";

export default function AdminSetup() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", bootstrapToken: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await axios.post(
        `${API_BASE}/admin/bootstrap`,
        { name: form.name, email: form.email, password: form.password },
        { headers: { "X-Admin-Bootstrap-Token": form.bootstrapToken } }
      );
      await login(form.email, form.password);
      navigate("/admin", { replace: true });
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
        "Administrator setup failed. Check the bootstrap configuration and try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  return (
    <main style={pageStyle}>
      <section style={{ maxWidth: "560px", margin: "0 auto" }}>
        <h1 style={{ color: "#f8fafc" }}>Administrator setup</h1>
        <p style={{ color: "#cbd5e1" }}>
          Create the first administrator. This one-time setup requires the bootstrap token configured by the backend operator.
        </p>
        <form onSubmit={handleSubmit} style={panelStyle}>
          {error && <p role="alert" style={{ color: "#fca5a5" }}>{error}</p>}
          <label style={labelStyle}>
            Administrator name
            <input value={form.name} onChange={updateField("name")} minLength={2} maxLength={100} required style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Email
            <input type="email" value={form.email} onChange={updateField("email")} maxLength={255} required style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Password (at least 12 characters)
            <input type="password" value={form.password} onChange={updateField("password")} minLength={12} maxLength={128} required style={inputStyle} />
          </label>
          <label style={labelStyle}>
            One-time bootstrap token
            <input type="password" value={form.bootstrapToken} onChange={updateField("bootstrapToken")} required autoComplete="off" style={inputStyle} />
          </label>
          <button type="submit" disabled={submitting} style={buttonStyle}>
            {submitting ? "Creating administrator..." : "Create first administrator"}
          </button>
        </form>
        <p><Link to="/login" style={{ color: "#38bdf8" }}>Back to login</Link></p>
      </section>
    </main>
  );
}

const pageStyle = {
  minHeight: "calc(100vh - 80px)",
  padding: "2rem",
  background: "#0f172a",
};
const panelStyle = {
  display: "grid",
  gap: "1rem",
  padding: "1.5rem",
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "0.75rem",
};
const labelStyle = {
  display: "grid",
  gap: "0.4rem",
  color: "#f8fafc",
};
const inputStyle = {
  boxSizing: "border-box",
  width: "100%",
  padding: "0.7rem",
  border: "1px solid #475569",
  borderRadius: "0.375rem",
  color: "#f8fafc",
  background: "#0f172a",
};
const buttonStyle = {
  padding: "0.75rem",
  border: "none",
  borderRadius: "0.375rem",
  color: "white",
  background: "#2563eb",
  cursor: "pointer",
};
