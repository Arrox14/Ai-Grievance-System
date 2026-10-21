import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const navLinkStyle = {
  color: "#cbd5e1",
  textDecoration: "none",
  padding: "0.5rem 1rem",
  borderRadius: "0.375rem",
  transition: "all 0.2s",
  background: "transparent",
  border: "none",
  cursor: "pointer",
  fontSize: "1rem",
  fontFamily: "inherit",
};

function handleNavOver(event) {
  event.currentTarget.style.background = "#1e293b";
  event.currentTarget.style.color = "#f8fafc";
}

function handleNavOut(event) {
  event.currentTarget.style.background = "transparent";
  event.currentTarget.style.color = "#cbd5e1";
}

function NavLink({ to, children, ...props }) {
  return (
    <Link
      to={to}
      style={navLinkStyle}
      onMouseOver={handleNavOver}
      onMouseOut={handleNavOut}
      {...props}
    >
      {children}
    </Link>
  );
}

export default function Navbar() {
  const { isAuthenticated, isCitizen, isAdmin, isOfficer, token, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const dashboardPath = "/dashboard";

  useEffect(() => {
    if (!isCitizen || !token) {
      return undefined;
    }

    let active = true;
    const fetchUnreadCount = async () => {
      try {
        const response = await axios.get(`${API_BASE}/notifications`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (active) setUnreadCount(response.data.unread_count);
      } catch (error) {
        console.error("Unable to fetch notification count:", error);
      }
    };

    const handleNotificationsChanged = () => fetchUnreadCount();
    fetchUnreadCount();
    window.addEventListener("pgis-notifications-changed", handleNotificationsChanged);
    return () => {
      active = false;
      window.removeEventListener("pgis-notifications-changed", handleNotificationsChanged);
    };
  }, [isCitizen, location.pathname, token]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <nav style={{
      padding: "1rem 2rem",
      background: "#0f172a",
      borderBottom: "1px solid #334155",
      boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
    }}>
      <div style={{
        maxWidth: "1200px",
        margin: "0 auto",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <Link to="/" style={{
          fontSize: "1.5rem",
          fontWeight: "bold",
          color: "#f8fafc",
          textDecoration: "none",
        }}>
          PGIS
        </Link>

        <div style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "flex-end",
        }}>
          <NavLink to="/">Home</NavLink>
          {isCitizen && <NavLink to="/upload">Submit Complaint</NavLink>}
          {isAuthenticated && <NavLink to={dashboardPath}>Dashboard</NavLink>}
          {isAdmin && <NavLink to="/admin">Admin</NavLink>}
          {isOfficer && (
            <NavLink to="/officer">Officer Dashboard</NavLink>
          )}
          {isCitizen && (
            <>
              <NavLink to="/my-complaints">My Complaints</NavLink>
              <NavLink to="/track">Track Complaint</NavLink>
              <NavLink to="/account">Account</NavLink>
            </>
          )}

          {isAuthenticated ? (
            <>
              <button
                type="button"
                onClick={handleLogout}
                style={navLinkStyle}
                onMouseOver={handleNavOver}
                onMouseOut={handleNavOut}
              >
                Logout
              </button>
              {isCitizen && (
                <NavLink
                  to="/notifications"
                  aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
                >
                  <span aria-hidden="true">🔔</span>
                  {unreadCount > 0 && (
                    <span style={{
                      marginLeft: "0.35rem",
                      padding: "0.1rem 0.4rem",
                      borderRadius: "999px",
                      background: "#ef4444",
                      color: "white",
                      fontSize: "0.75rem",
                    }}>
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                  )}
                </NavLink>
              )}
            </>
          ) : (
            <>
              <NavLink to="/login">Login</NavLink>
              <NavLink to="/register">Register</NavLink>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
