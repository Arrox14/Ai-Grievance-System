import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const messageStyle = {
  minHeight: "calc(100vh - 80px)",
  padding: "2rem",
  background: "#0f172a",
  color: "#f8fafc",
  display: "grid",
  placeContent: "center",
  textAlign: "center",
};

export default function ProtectedRoute({ children, allowedRoles }) {
  const {
    ready,
    token,
    isAuthenticated,
    user,
    sessionError,
    sessionExpired,
    retrySession,
  } = useAuth();
  const location = useLocation();

  if (!ready) {
    return <main style={messageStyle} role="status">Checking your session...</main>;
  }

  if (sessionError && token) {
    return (
      <main style={messageStyle} role="alert">
        <h1>Unable to verify your session</h1>
        <p>{sessionError}</p>
        <button type="button" onClick={retrySession}>Retry</button>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: `${location.pathname}${location.search}`,
          sessionExpired,
        }}
      />
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <main style={messageStyle} role="alert">
        <h1>Access denied</h1>
        <p>Your account does not have permission to view this page.</p>
        <Link to="/dashboard" style={{ color: "#38bdf8" }}>Go to your dashboard</Link>
      </main>
    );
  }

  return children;
}
