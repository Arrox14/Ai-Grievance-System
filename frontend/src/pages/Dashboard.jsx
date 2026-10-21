import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();

  if (user?.role === "admin") return <Navigate to="/admin" replace />;
  if (user?.role === "officer") return <Navigate to="/officer" replace />;
  return <Navigate to="/my-complaints" replace />;
}
