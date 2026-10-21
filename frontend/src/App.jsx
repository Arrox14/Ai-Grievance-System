import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Upload from "./pages/Upload";
import Dashboard from "./pages/Dashboard";
import Admin from "./pages/Admin";
import AdminComplaintDetails from "./pages/AdminComplaintDetails";
import Login from "./pages/Login";
import AdminSetup from "./pages/AdminSetup";
import Register from "./pages/Register";
import Account from "./pages/Account";
import ComplaintHistory from "./pages/ComplaintHistory";
import ComplaintDetails from "./pages/ComplaintDetails";
import ComplaintTracking from "./pages/ComplaintTracking";
import Notifications from "./pages/Notifications";
import OfficerDashboard from "./pages/OfficerDashboard";
import OfficerComplaintDetails from "./pages/OfficerComplaintDetails";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthProvider";

export default function App() {
  return (
    <AuthProvider>
      <Navbar />

      <Routes>
        <Route path="/" element={<Home />} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <Upload />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Admin />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/complaints/:complaintId"
          element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminComplaintDetails />
            </ProtectedRoute>
          }
        />
        <Route
          path="/officer"
          element={
            <ProtectedRoute allowedRoles={["officer"]}>
              <OfficerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/officer-dashboard"
          element={
            <ProtectedRoute allowedRoles={["officer"]}>
              <OfficerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/officer/complaints/:complaintId"
          element={
            <ProtectedRoute allowedRoles={["officer"]}>
              <OfficerComplaintDetails />
            </ProtectedRoute>
          }
        />
        <Route
          path="/officer-dashboard/complaints/:complaintId"
          element={
            <ProtectedRoute allowedRoles={["officer"]}>
              <OfficerComplaintDetails />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<Login />} />
        <Route path="/officer-login" element={<Login />} />
        <Route path="/admin-login" element={<Login />} />
        <Route path="/admin-setup" element={<AdminSetup />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/account"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <Account />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-complaints"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <ComplaintHistory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-complaints/:complaintId"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <ComplaintDetails />
            </ProtectedRoute>
          }
        />
        <Route
          path="/track"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <ComplaintTracking />
            </ProtectedRoute>
          }
        />
        <Route
          path="/notifications"
          element={
            <ProtectedRoute allowedRoles={["citizen"]}>
              <Notifications />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  );
}
