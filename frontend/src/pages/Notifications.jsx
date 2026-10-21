import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";

export default function Notifications() {
  const { token } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [updatingId, setUpdatingId] = useState(null);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await axios.get(`${API_BASE}/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications(response.data.notifications);
      setUnreadCount(response.data.unread_count);
    } catch {
      setError("Unable to load notifications. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications, retry]);

  const markAsRead = async (notificationId) => {
    setUpdatingId(notificationId);
    try {
      await axios.patch(
        `${API_BASE}/notifications/${notificationId}/read`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNotifications((current) =>
        current.map((notification) =>
          notification.id === notificationId
            ? { ...notification, is_read: true }
            : notification
        )
      );
      setUnreadCount((count) =>
        notifications.find((item) => item.id === notificationId && !item.is_read)
          ? Math.max(0, count - 1)
          : count
      );
      window.dispatchEvent(new Event("pgis-notifications-changed"));
    } catch {
      setError("Unable to mark this notification as read. Please retry.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <main
      style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
        color: "#f8fafc",
      }}
    >
      <section style={{ maxWidth: "900px", margin: "0 auto" }}>
        <h1 style={{ fontSize: "2rem", margin: "0 0 1.5rem" }}>
          Notifications
        </h1>
        {!loading && !error && (
          <p style={{ color: "#94a3b8" }}>
            {unreadCount} unread {unreadCount === 1 ? "notification" : "notifications"}
          </p>
        )}

        {loading ? (
          <p role="status" style={{ color: "#cbd5e1" }}>
            Loading notifications...
          </p>
        ) : error && notifications.length === 0 ? (
          <div role="alert" style={messagePanelStyle}>
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} style={buttonStyle}>
              Retry
            </button>
          </div>
        ) : notifications.length === 0 ? (
          <div style={messagePanelStyle}>You have no notifications yet.</div>
        ) : (
          <>
            {error && (
              <p role="alert" style={{ color: "#fca5a5" }}>
                {error}
              </p>
            )}
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {notifications.map((notification) => (
                <li
                  key={notification.id}
                  style={{
                    ...messagePanelStyle,
                    marginBottom: "0.75rem",
                    borderColor: notification.is_read ? "#334155" : "#3b82f6",
                    opacity: notification.is_read ? 0.8 : 1,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: "1rem",
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      {notification.complaint_id ? (
                        <Link
                          to={`/my-complaints/${notification.complaint_id}`}
                          style={{ color: "#f8fafc", fontWeight: "600" }}
                        >
                          {notification.title} — Complaint #{notification.complaint_id}
                        </Link>
                      ) : (
                        <strong style={{ color: "#f8fafc" }}>
                          {notification.title}
                        </strong>
                      )}
                      <p style={{ color: "#cbd5e1", margin: "0.5rem 0" }}>
                        {notification.message}
                      </p>
                      <time
                        dateTime={notification.created_at}
                        style={{ color: "#94a3b8", fontSize: "0.875rem" }}
                      >
                        {new Date(notification.created_at).toLocaleString()}
                      </time>
                    </div>
                    {!notification.is_read && (
                      <button
                        type="button"
                        disabled={updatingId === notification.id}
                        onClick={() => markAsRead(notification.id)}
                        style={buttonStyle}
                      >
                        {updatingId === notification.id ? "Saving..." : "Mark as read"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </main>
  );
}

const messagePanelStyle = {
  padding: "1rem",
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "0.75rem",
  color: "#cbd5e1",
};

const buttonStyle = {
  background: "#3b82f6",
  color: "white",
  border: "none",
  padding: "0.6rem 1rem",
  borderRadius: "0.375rem",
  cursor: "pointer",
};
