import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav style={{
      padding: "1rem 2rem",
      background: "#0f172a",
      borderBottom: "1px solid #334155",
      boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
    }}>
      <div style={{
        maxWidth: "1200px",
        margin: "0 auto",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <Link 
          to="/" 
          style={{
            fontSize: "1.5rem",
            fontWeight: "bold",
            color: "#f8fafc",
            textDecoration: "none"
          }}
        >
          PGIS
        </Link>
        
        <div style={{ display: "flex", gap: "2rem" }}>
          <Link 
            to="/" 
            style={{
              color: "#cbd5e1",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "0.375rem",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.target.style.background = "#1e293b";
              e.target.style.color = "#f8fafc";
            }}
            onMouseOut={(e) => {
              e.target.style.background = "transparent";
              e.target.style.color = "#cbd5e1";
            }}
          >
            Home
          </Link>
          <Link 
            to="/upload" 
            style={{
              color: "#cbd5e1",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "0.375rem",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.target.style.background = "#1e293b";
              e.target.style.color = "#f8fafc";
            }}
            onMouseOut={(e) => {
              e.target.style.background = "transparent";
              e.target.style.color = "#cbd5e1";
            }}
          >
            Upload
          </Link>
          <Link 
            to="/dashboard" 
            style={{
              color: "#cbd5e1",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "0.375rem",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.target.style.background = "#1e293b";
              e.target.style.color = "#f8fafc";
            }}
            onMouseOut={(e) => {
              e.target.style.background = "transparent";
              e.target.style.color = "#cbd5e1";
            }}
          >
            Dashboard
          </Link>
          <Link 
            to="/admin" 
            style={{
              color: "#cbd5e1",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "0.375rem",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.target.style.background = "#1e293b";
              e.target.style.color = "#f8fafc";
            }}
            onMouseOut={(e) => {
              e.target.style.background = "transparent";
              e.target.style.color = "#cbd5e1";
            }}
          >
            Admin
          </Link>
        </div>
      </div>
    </nav>
  );
}