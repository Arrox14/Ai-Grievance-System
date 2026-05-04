import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div style={{
      minHeight: "calc(100vh - 80px)",
      background: "#0f172a",
      padding: "2rem"
    }}>
      <div style={{
        maxWidth: "1200px",
        margin: "0 auto"
      }}>
        <div style={{
          textAlign: "center",
          marginBottom: "3rem"
        }}>
          <h1 style={{
            fontSize: "3rem",
            fontWeight: "bold",
            color: "#f8fafc",
            margin: "0 0 1rem 0",
            lineHeight: "1.2"
          }}>
            Public Grievance Intelligence System
          </h1>
          <p style={{
            fontSize: "1.25rem",
            color: "#cbd5e1",
            margin: "0 0 2rem 0",
            maxWidth: "600px",
            marginLeft: "auto",
            marginRight: "auto",
            lineHeight: "1.6"
          }}>
            Submit and monitor complaints with AI-based classification and intelligent analysis for faster resolution.
          </p>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "2rem",
          marginBottom: "3rem"
        }}>
          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
            textAlign: "center",
            transition: "transform 0.2s, box-shadow 0.2s"
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 24px rgba(0, 0, 0, 0.15)";
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.1)";
          }}
          >
            <div style={{
              width: "60px",
              height: "60px",
              background: "#3b82f6",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1rem auto",
              fontSize: "1.5rem",
              color: "white",
              fontWeight: "bold"
            }}>
              1
            </div>
            <h3 style={{
              color: "#f8fafc",
              margin: "0 0 1rem 0",
              fontSize: "1.25rem",
              fontWeight: "600"
            }}>
              Submit Complaint
            </h3>
            <p style={{
              color: "#94a3b8",
              margin: "0 0 1.5rem 0",
              lineHeight: "1.5"
            }}>
              File your grievance with text, images, or video evidence and location data.
            </p>
            <Link
              to="/upload"
              style={{
                display: "inline-block",
                background: "#3b82f6",
                color: "white",
                padding: "0.75rem 1.5rem",
                borderRadius: "0.5rem",
                textDecoration: "none",
                fontWeight: "500",
                transition: "background 0.2s"
              }}
              onMouseOver={(e) => {
                e.target.style.background = "#2563eb";
              }}
              onMouseOut={(e) => {
                e.target.style.background = "#3b82f6";
              }}
            >
              File Complaint
            </Link>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
            textAlign: "center",
            transition: "transform 0.2s, box-shadow 0.2s"
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 24px rgba(0, 0, 0, 0.15)";
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.1)";
          }}
          >
            <div style={{
              width: "60px",
              height: "60px",
              background: "#10b981",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1rem auto",
              fontSize: "1.5rem",
              color: "white",
              fontWeight: "bold"
            }}>
              2
            </div>
            <h3 style={{
              color: "#f8fafc",
              margin: "0 0 1rem 0",
              fontSize: "1.25rem",
              fontWeight: "600"
            }}>
              AI Analysis
            </h3>
            <p style={{
              color: "#94a3b8",
              margin: "0 0 1.5rem 0",
              lineHeight: "1.5"
            }}>
              Automatic categorization and priority assignment using machine learning models.
            </p>
            <div style={{
              color: "#10b981",
              fontWeight: "500"
            }}>
              Powered by ML
            </div>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
            textAlign: "center",
            transition: "transform 0.2s, box-shadow 0.2s"
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 24px rgba(0, 0, 0, 0.15)";
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.1)";
          }}
          >
            <div style={{
              width: "60px",
              height: "60px",
              background: "#f59e0b",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1rem auto",
              fontSize: "1.5rem",
              color: "white",
              fontWeight: "bold"
            }}>
              3
            </div>
            <h3 style={{
              color: "#f8fafc",
              margin: "0 0 1rem 0",
              fontSize: "1.25rem",
              fontWeight: "600"
            }}>
              Track Progress
            </h3>
            <p style={{
              color: "#94a3b8",
              margin: "0 0 1.5rem 0",
              lineHeight: "1.5"
            }}>
              Monitor your complaint status and view resolution progress in real-time.
            </p>
            <Link
              to="/dashboard"
              style={{
                display: "inline-block",
                background: "#f59e0b",
                color: "white",
                padding: "0.75rem 1.5rem",
                borderRadius: "0.5rem",
                textDecoration: "none",
                fontWeight: "500",
                transition: "background 0.2s"
              }}
              onMouseOver={(e) => {
                e.target.style.background = "#d97706";
              }}
              onMouseOut={(e) => {
                e.target.style.background = "#f59e0b";
              }}
            >
              View Dashboard
            </Link>
          </div>
        </div>

        <div style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "0.75rem",
          padding: "2rem",
          textAlign: "center"
        }}>
          <h2 style={{
            color: "#f8fafc",
            margin: "0 0 1rem 0",
            fontSize: "1.5rem",
            fontWeight: "600"
          }}>
            System Features
          </h2>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "2rem",
            marginTop: "2rem"
          }}>
            <div>
              <h4 style={{ color: "#3b82f6", margin: "0 0 0.5rem 0" }}>AI Classification</h4>
              <p style={{ color: "#94a3b8", margin: "0", fontSize: "0.875rem" }}>
                Automatic categorization and priority assignment
              </p>
            </div>
            <div>
              <h4 style={{ color: "#10b981", margin: "0 0 0.5rem 0" }}>Image Analysis</h4>
              <p style={{ color: "#94a3b8", margin: "0", fontSize: "0.875rem" }}>
                YOLOv8 powered object detection
              </p>
            </div>
            <div>
              <h4 style={{ color: "#f59e0b", margin: "0 0 0.5rem 0" }}>Location Tracking</h4>
              <p style={{ color: "#94a3b8", margin: "0", fontSize: "0.875rem" }}>
                GPS coordinates for precise complaint location
              </p>
            </div>
            <div>
              <h4 style={{ color: "#ef4444", margin: "0 0 0.5rem 0" }}>Real-time Status</h4>
              <p style={{ color: "#94a3b8", margin: "0", fontSize: "0.875rem" }}>
                Live tracking of complaint resolution
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}