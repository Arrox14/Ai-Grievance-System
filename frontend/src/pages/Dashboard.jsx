import { useEffect, useState } from "react";
import axios from "axios";

export default function Dashboard() {
  const [data, setData] = useState([]);

  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/complaints")
      .then((res) => setData(res.data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div style={{ padding: "30px", background: "#0f172a", minHeight: "100vh", color: "white" }}>
      <h2 style={{ marginBottom: "20px" }}>📊 Complaint Dashboard</h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "20px"
        }}
      >
        {data.map((item) => (
          <div
            key={item.id}
            style={{
              background: "#1e293b",
              padding: "20px",
              borderRadius: "12px",
              boxShadow: "0 4px 10px rgba(0,0,0,0.3)",
            }}
          >
            <p><b>Complaint:</b> {item.text}</p>

            <p>
              <b>Category:</b>{" "}
              <span style={{ color: "#38bdf8" }}>{item.category}</span>
            </p>

            <p>
              <b>Priority:</b>{" "}
              <span
                style={{
                  color:
                    item.priority === "high"
                      ? "red"
                      : item.priority === "medium"
                      ? "orange"
                      : "green",
                }}
              >
                {item.priority}
              </span>
            </p>

            <p>
              <b>Status:</b>{" "}
              <span
                style={{
                  color: item.status === "Pending" ? "orange" : "green",
                }}
              >
                {item.status}
              </span>
            </p>

            <p>
              <b>Time:</b>{" "}
              {item.timestamp
                ? new Date(item.timestamp).toLocaleString()
                : "N/A"}
            </p>

            {/* 📍 Location */}
            {(item.latitude !== 0 || item.longitude !== 0) && (
              <p>
                <b>Location:</b> {item.latitude}, {item.longitude}
              </p>
            )}

            {/* 🖼️ Image / Video Preview */}
            {item.file_path && (
              <div style={{ marginTop: "10px" }}>
                {item.file_path.endsWith(".mp4") ? (
                  <video
                    src={`http://127.0.0.1:8000/${item.file_path}`}
                    controls
                    style={{ width: "100%", borderRadius: "8px" }}
                  />
                ) : (
                  <img
                    src={`http://127.0.0.1:8000/${item.file_path}`}
                    alt="complaint"
                    style={{ width: "100%", borderRadius: "8px" }}
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}