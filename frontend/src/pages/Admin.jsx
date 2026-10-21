import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const buttonStyle = {
  color: "white",
  border: "none",
  padding: "0.5rem 0.75rem",
  borderRadius: "0.375rem",
  cursor: "pointer",
};

export default function Admin() {
  const { token } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [complaintsError, setComplaintsError] = useState("");
  const [filter, setFilter] = useState({
    search: "",
    category: "",
    priority: "",
    status: "",
    date_from: "",
    date_to: "",
    department_id: "",
    officer_id: "",
    sort: "newest",
  });
  const [categories, setCategories] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [pageInfo, setPageInfo] = useState({ total: 0, page: 1, page_size: 20 });
  const [serverStats, setServerStats] = useState({
    total: 0, pending: 0, in_progress: 0, resolved: 0, high: 0,
  });
  const complaintRequestId = useRef(0);
  const [officers, setOfficers] = useState([]);
  const [officerForm, setOfficerForm] = useState({ name: "", email: "", password: "" });
  const [creatingOfficer, setCreatingOfficer] = useState(false);
  const [selectedOfficers, setSelectedOfficers] = useState({});
  const [assigningId, setAssigningId] = useState(null);
  const [selectedStatuses, setSelectedStatuses] = useState({});
  const [updatingStatusId, setUpdatingStatusId] = useState(null);
  const [resolutionSubmissions, setResolutionSubmissions] = useState([]);
  const [resolutionLoading, setResolutionLoading] = useState(true);
  const [resolutionError, setResolutionError] = useState("");
  const [reviewingSubmissionId, setReviewingSubmissionId] = useState(null);

  const fetchComplaints = useCallback(async () => {
    const requestId = ++complaintRequestId.current;
    setComplaintsError("");
    try {
      setLoading(true);
      const params = new URLSearchParams();
      Object.entries(filter).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });
      params.append("page", String(pageInfo.page));
      params.append("page_size", String(pageInfo.page_size));
      
      const response = await axios.get(
        `${API_BASE}/admin/complaints?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (requestId !== complaintRequestId.current) return;
      setComplaints(response.data.items);
      setPageInfo((current) => ({ ...current, total: response.data.total }));
      setServerStats(response.data.stats);
    } catch (error) {
      if (requestId !== complaintRequestId.current) return;
      console.error("Error fetching complaints:", error);
      setComplaintsError(
        error.response?.data?.detail || "Failed to load complaints. Please try again."
      );
    } finally {
      if (requestId === complaintRequestId.current) setLoading(false);
    }
  }, [filter, pageInfo.page, pageInfo.page_size, token]);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  const fetchOfficers = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE}/admin/complaint-filter-options`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOfficers(response.data.officers);
      setCategories(response.data.categories);
      setDepartments(response.data.departments);
    } catch (error) {
      console.error("Error fetching officers:", error);
    }
  }, [token]);

  useEffect(() => {
    fetchOfficers();
  }, [fetchOfficers]);

  const fetchResolutionSubmissions = useCallback(async () => {
    setResolutionLoading(true);
    setResolutionError("");
    try {
      const response = await axios.get("http://127.0.0.1:8000/admin/resolution-submissions", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setResolutionSubmissions(response.data);
    } catch (error) {
      console.error("Error fetching resolution submissions:", error);
      setResolutionError(error.response?.data?.detail || "Unable to load resolution submissions.");
    } finally {
      setResolutionLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchResolutionSubmissions();
  }, [fetchResolutionSubmissions]);

  const handleCreateOfficer = async (event) => {
    event.preventDefault();
    setCreatingOfficer(true);
    try {
      await axios.post(
        "http://127.0.0.1:8000/admin/officers",
        officerForm,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setOfficerForm({ name: "", email: "", password: "" });
      await fetchOfficers();
      window.alert("Officer account created successfully.");
    } catch (error) {
      console.error("Error creating officer:", error);
      window.alert(error.response?.data?.detail || "Unable to create officer.");
    } finally {
      setCreatingOfficer(false);
    }
  };

  const handleAssignOfficer = async (complaintId) => {
    const officerId = selectedOfficers[complaintId];
    if (!officerId) return;
    setAssigningId(complaintId);
    try {
      const response = await axios.put(
        `http://127.0.0.1:8000/admin/complaints/${complaintId}/assignment`,
        { officer_id: Number(officerId) },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setComplaints((current) =>
        current.map((complaint) =>
          complaint.id === complaintId
            ? {
                ...complaint,
                assigned_officer_id: Number(officerId),
                assigned_officer: officers.find((officer) => officer.id === Number(officerId))?.name,
                department_id: officers.find((officer) => officer.id === Number(officerId))?.department_id ?? null,
                department: officers.find((officer) => officer.id === Number(officerId))?.department ?? null,
                assigned_at: response.data.assigned_at,
              }
            : complaint
        )
      );
      window.alert("Complaint assigned successfully.");
    } catch (error) {
      console.error("Error assigning complaint:", error);
      window.alert(error.response?.data?.detail || "Unable to assign complaint.");
    } finally {
      setAssigningId(null);
    }
  };

  const handleUpdateStatus = async (complaint) => {
    const status = selectedStatuses[complaint.id] ?? complaint.status;
    if (status === complaint.status) return;
    const remarks = window.prompt("Add optional remarks for this status change:");
    if (remarks === null) return;

    setUpdatingStatusId(complaint.id);
    try {
      const response = await axios.put(
        `${API_BASE}/update-status/${encodeURIComponent(complaint.id)}`,
        { status, remarks },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setComplaints((current) => current.map((item) => (
        item.id === complaint.id ? { ...item, status } : item
      )));
      setSelectedStatuses((current) => ({ ...current, [complaint.id]: status }));
      await fetchComplaints();
      window.alert(response.data.message || "Complaint status updated successfully.");
    } catch (error) {
      console.error("Error updating complaint status:", error);
      window.alert(error.response?.data?.detail || "Unable to update complaint status.");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const handleFilterChange = (key, value) => {
    setPageInfo((current) => ({ ...current, page: 1 }));
    setFilter((prev) => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    fetchComplaints();
  };

  const clearFilters = () => {
    setPageInfo((current) => ({ ...current, page: 1 }));
    setFilter({
      search: "",
      category: "",
      priority: "",
      status: "",
      date_from: "",
      date_to: "",
      department_id: "",
      officer_id: "",
      sort: "newest",
    });
  };

  const reviewResolution = async (submission, decision) => {
    const remarks = decision === "reject"
      ? window.prompt("Reason for rejecting this resolution submission (optional):")
      : window.prompt("Administrator review remarks (optional):");
    if (remarks === null) return;
    setReviewingSubmissionId(submission.id);
    try {
      await axios.post(
        `http://127.0.0.1:8000/admin/resolution-submissions/${submission.id}/${decision}`,
        { remarks },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await Promise.all([fetchResolutionSubmissions(), fetchComplaints()]);
      window.alert(decision === "approve"
        ? "Resolution approved; complaint marked resolved."
        : "Resolution submission rejected.");
    } catch (error) {
      console.error(`Error ${decision}ing resolution submission:`, error);
      window.alert(error.response?.data?.detail || "Unable to review resolution submission.");
    } finally {
      setReviewingSubmissionId(null);
    }
  };

  const downloadResolutionAttachment = async (submission) => {
    try {
      const response = await axios.get(
        `http://127.0.0.1:8000${submission.attachment_url}`,
        { headers: { Authorization: `Bearer ${token}` }, responseType: "blob" }
      );
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = submission.attachment_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) {
      window.alert(error.response?.data?.detail || "Unable to download resolution attachment.");
    }
  };

  const stats = {
    total: serverStats.total,
    pending: serverStats.pending,
    inProgress: serverStats.in_progress,
    resolved: serverStats.resolved,
    high: serverStats.high,
  };

  if (loading) {
    return (
      <div style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
        display: "flex",
        justifyContent: "center",
        alignItems: "center"
      }}>
        <div style={{ color: "#f8fafc", fontSize: "1.25rem" }}>
          Loading complaints...
        </div>
      </div>
    );
  }

  if (complaintsError) {
    return (
      <div style={{
        minHeight: "calc(100vh - 80px)",
        background: "#0f172a",
        padding: "2rem",
      }}>
        <section style={{
          maxWidth: "800px",
          margin: "0 auto",
          padding: "1.5rem",
          background: "#1e293b",
          border: "1px solid #7f1d1d",
          borderRadius: "0.75rem",
          color: "#f8fafc",
        }}>
          <h1>Unable to load Admin Dashboard</h1>
          <p role="alert">{complaintsError}</p>
          <button type="button" onClick={fetchComplaints} style={buttonStyle}>
            Retry
          </button>
        </section>
      </div>
    );
  }

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
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "2rem"
        }}>
          <h1 style={{
            color: "#f8fafc",
            fontSize: "2rem",
            fontWeight: "bold",
            margin: 0
          }}>
            Admin Panel
          </h1>
          <div style={{
            background: "#ef4444",
            color: "white",
            padding: "0.5rem 1rem",
            borderRadius: "0.375rem",
            fontSize: "0.875rem",
            fontWeight: "600"
          }}>
            Administrator Access
          </div>
        </div>

        <section style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "0.75rem",
          padding: "1.5rem",
          marginBottom: "2rem"
        }}>
          <h3 style={{ color: "#f8fafc", margin: "0 0 1rem", fontSize: "1.125rem" }}>
            Create Officer Account
          </h3>
          <form
            onSubmit={handleCreateOfficer}
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "0.75rem",
            }}
          >
            {[
              ["name", "Officer name", "text"],
              ["email", "Email", "email"],
              ["password", "Temporary password", "password"],
            ].map(([field, label, type]) => (
              <input
                key={field}
                aria-label={label}
                type={type}
                placeholder={label}
                minLength={field === "password" ? 8 : undefined}
                required
                value={officerForm[field]}
                onChange={(event) =>
                  setOfficerForm((current) => ({
                    ...current,
                    [field]: event.target.value,
                  }))
                }
                style={{
                  padding: "0.65rem",
                  background: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "0.375rem",
                  color: "#f8fafc",
                }}
              />
            ))}
            <button type="submit" disabled={creatingOfficer} style={{
              background: "#3b82f6", color: "white", border: "none",
              padding: "0.65rem 1rem", borderRadius: "0.375rem",
              cursor: creatingOfficer ? "not-allowed" : "pointer",
            }}>
              {creatingOfficer ? "Creating..." : "Create Officer"}
            </button>
          </form>
        </section>

        <section style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "0.75rem",
          padding: "1.5rem",
          marginBottom: "2rem",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center" }}>
            <h2 style={{ color: "#f8fafc", margin: 0 }}>
              Resolution Review ({resolutionSubmissions.length})
            </h2>
            <button type="button" onClick={fetchResolutionSubmissions} style={{
              background: "#334155", color: "#f8fafc", border: "1px solid #475569",
              padding: "0.5rem 0.75rem", borderRadius: "0.375rem", cursor: "pointer",
            }}>
              Refresh
            </button>
          </div>
          {resolutionLoading ? (
            <p role="status" style={{ color: "#cbd5e1" }}>Loading resolution submissions...</p>
          ) : resolutionError ? (
            <div role="alert" style={{ color: "#fca5a5", marginTop: "1rem" }}>
              <p>{resolutionError}</p>
              <button type="button" onClick={fetchResolutionSubmissions}>Retry</button>
            </div>
          ) : resolutionSubmissions.length === 0 ? (
            <p style={{ color: "#cbd5e1" }}>No resolution submissions are awaiting review.</p>
          ) : (
            resolutionSubmissions.map((submission) => (
              <article key={submission.id} style={{
                borderTop: "1px solid #334155", marginTop: "1rem", paddingTop: "1rem",
                color: "#cbd5e1",
              }}>
                <h3 style={{ color: "#f8fafc", margin: "0 0 0.5rem" }}>
                  Complaint #{submission.complaint_id}
                </h3>
                <p>Submitted by {submission.officer_name} · {new Date(submission.submitted_at).toLocaleString()}</p>
                <p>Resolution date: {submission.resolution_date}</p>
                <p><strong>Findings:</strong> {submission.findings}</p>
                <p><strong>Resolution remarks:</strong> {submission.remarks}</p>
                <p>
                  Attachment: {submission.attachment_name} ({(submission.file_size / 1024 / 1024).toFixed(2)} MB)
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => downloadResolutionAttachment(submission)}
                    style={{ ...buttonStyle, background: "#334155" }}
                  >
                    Download attachment
                  </button>
                  <button
                    type="button"
                    disabled={reviewingSubmissionId === submission.id}
                    onClick={() => reviewResolution(submission, "approve")}
                    style={{ ...buttonStyle, background: "#059669" }}
                  >
                    {reviewingSubmissionId === submission.id ? "Reviewing..." : "Approve and resolve"}
                  </button>
                  <button
                    type="button"
                    disabled={reviewingSubmissionId === submission.id}
                    onClick={() => reviewResolution(submission, "reject")}
                    style={{ ...buttonStyle, background: "#dc2626" }}
                  >
                    Reject submission
                  </button>
                </div>
              </article>
            ))
          )}
        </section>

        {/* Statistics Cards */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "1rem",
          marginBottom: "2rem"
        }}>
          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            padding: "1rem",
            textAlign: "center"
          }}>
            <div style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              color: "#3b82f6",
              marginBottom: "0.25rem"
            }}>
              {stats.total}
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "0.875rem" }}>Total</div>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            padding: "1rem",
            textAlign: "center"
          }}>
            <div style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              color: "#f59e0b",
              marginBottom: "0.25rem"
            }}>
              {stats.pending}
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "0.875rem" }}>Pending</div>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            padding: "1rem",
            textAlign: "center"
          }}>
            <div style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              color: "#3b82f6",
              marginBottom: "0.25rem"
            }}>
              {stats.inProgress}
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "0.875rem" }}>In Progress</div>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            padding: "1rem",
            textAlign: "center"
          }}>
            <div style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              color: "#10b981",
              marginBottom: "0.25rem"
            }}>
              {stats.resolved}
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "0.875rem" }}>Resolved</div>
          </div>

          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            padding: "1rem",
            textAlign: "center"
          }}>
            <div style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              color: "#dc2626",
              marginBottom: "0.25rem"
            }}>
              {stats.high}
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "0.875rem" }}>High Priority</div>
          </div>
        </div>

        {/* Filters */}
        <div style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "0.75rem",
          padding: "1.5rem",
          marginBottom: "2rem"
        }}>
          <h3 style={{
            color: "#f8fafc",
            margin: "0 0 1rem 0",
            fontSize: "1.125rem",
            fontWeight: "600"
          }}>
            Filter Complaints
          </h3>
          
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "1rem",
            marginBottom: "1rem"
          }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{
                display: "block",
                color: "#cbd5e1",
                marginBottom: "0.5rem",
                fontSize: "0.875rem"
              }}>
                Search complaints
              </label>
              <input
                type="search"
                value={filter.search}
                onChange={(event) => handleFilterChange("search", event.target.value)}
                placeholder="ID, description, category, officer..."
                aria-label="Search complaints"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "0.5rem",
                  background: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "0.375rem",
                  color: "#f8fafc",
                  fontSize: "0.875rem"
                }}
              />
            </div>
            <div>
              <label style={{
                display: "block",
                color: "#cbd5e1",
                marginBottom: "0.5rem",
                fontSize: "0.875rem"
              }}>
                Category
              </label>
              <select
                value={filter.category}
                onChange={(e) => handleFilterChange("category", e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  background: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "0.375rem",
                  color: "#f8fafc",
                  fontSize: "0.875rem"
                }}
              >
                <option value="">All Categories</option>
                {categories.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{
                display: "block",
                color: "#cbd5e1",
                marginBottom: "0.5rem",
                fontSize: "0.875rem"
              }}>
                Priority
              </label>
              <select
                value={filter.priority}
                onChange={(e) => handleFilterChange("priority", e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  background: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "0.375rem",
                  color: "#f8fafc",
                  fontSize: "0.875rem"
                }}
              >
                <option value="">All Priorities</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>

            <div>
              <label style={{
                display: "block",
                color: "#cbd5e1",
                marginBottom: "0.5rem",
                fontSize: "0.875rem"
              }}>
                Status
              </label>
              <select
                value={filter.status}
                onChange={(e) => handleFilterChange("status", e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  background: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "0.375rem",
                  color: "#f8fafc",
                  fontSize: "0.875rem"
                }}
              >
                <option value="">All Statuses</option>
                <option value="Pending">Pending</option>
                <option value="In Progress">In Progress</option>
                <option value="Resolved">Resolved</option>
              </select>
            </div>
            <div>
              <label style={{ display: "block", color: "#cbd5e1", marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                Department
              </label>
              <select
                value={filter.department_id}
                onChange={(event) => handleFilterChange("department_id", event.target.value)}
                style={{
                  width: "100%", padding: "0.5rem", background: "#0f172a",
                  border: "1px solid #475569", borderRadius: "0.375rem",
                  color: "#f8fafc", fontSize: "0.875rem"
                }}
              >
                <option value="">All Departments</option>
                {departments.map((department) => (
                  <option key={department.id} value={department.id}>{department.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ display: "block", color: "#cbd5e1", marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                Assigned officer
              </label>
              <select
                value={filter.officer_id}
                onChange={(event) => handleFilterChange("officer_id", event.target.value)}
                style={{
                  width: "100%", padding: "0.5rem", background: "#0f172a",
                  border: "1px solid #475569", borderRadius: "0.375rem",
                  color: "#f8fafc", fontSize: "0.875rem"
                }}
              >
                <option value="">All Officers</option>
                {officers.map((officer) => (
                  <option key={officer.id} value={officer.id}>{officer.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ display: "block", color: "#cbd5e1", marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                Submitted from
              </label>
              <input
                type="date"
                value={filter.date_from}
                onChange={(event) => handleFilterChange("date_from", event.target.value)}
                style={{
                  width: "100%", boxSizing: "border-box", padding: "0.5rem",
                  background: "#0f172a", border: "1px solid #475569",
                  borderRadius: "0.375rem", color: "#f8fafc", fontSize: "0.875rem"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", color: "#cbd5e1", marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                Submitted through
              </label>
              <input
                type="date"
                value={filter.date_to}
                onChange={(event) => handleFilterChange("date_to", event.target.value)}
                style={{
                  width: "100%", boxSizing: "border-box", padding: "0.5rem",
                  background: "#0f172a", border: "1px solid #475569",
                  borderRadius: "0.375rem", color: "#f8fafc", fontSize: "0.875rem"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", color: "#cbd5e1", marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                Sort by
              </label>
              <select
                value={filter.sort}
                onChange={(event) => handleFilterChange("sort", event.target.value)}
                style={{
                  width: "100%", padding: "0.5rem", background: "#0f172a",
                  border: "1px solid #475569", borderRadius: "0.375rem",
                  color: "#f8fafc", fontSize: "0.875rem"
                }}
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="priority">Priority</option>
                <option value="status">Status</option>
              </select>
            </div>
          </div>

          <div style={{ display: "flex", gap: "1rem" }}>
            <button
              onClick={applyFilters}
              style={{
                background: "#3b82f6",
                color: "white",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "0.375rem",
                cursor: "pointer",
                fontWeight: "500",
                fontSize: "0.875rem"
              }}
            >
              Apply Filters
            </button>
            <button
              onClick={clearFilters}
              style={{
                background: "#64748b",
                color: "white",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "0.375rem",
                cursor: "pointer",
                fontWeight: "500",
                fontSize: "0.875rem"
              }}
            >
              Clear Filters
            </button>
          </div>
        </div>

        {/* Complaints List */}
        <div>
          <h3 style={{
            color: "#f8fafc",
            margin: "0 0 1rem 0",
            fontSize: "1.125rem",
            fontWeight: "600"
          }}>
            Manage Complaints ({pageInfo.total})
          </h3>

          <div style={{
            overflowX: "auto",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            marginBottom: "1rem",
          }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "850px" }}>
              <thead>
                <tr style={{ color: "#cbd5e1", textAlign: "left", background: "#0f172a" }}>
                  {["Complaint ID", "Category", "Description", "Priority", "Status", "Submitted", "Assigned officer", ""].map((heading) => (
                    <th key={heading || "details"} scope="col" style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {complaints.map((complaint) => (
                  <tr key={complaint.id} style={{ color: "#f8fafc" }}>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>#{complaint.id}</td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>{complaint.category}</td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155", maxWidth: "300px" }}>
                      {complaint.text.length > 120 ? `${complaint.text.slice(0, 120)}...` : complaint.text}
                    </td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>{complaint.priority}</td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>{complaint.status}</td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155", whiteSpace: "nowrap" }}>
                      {new Date(complaint.timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>
                      {complaint.assigned_officer || "Unassigned"}
                    </td>
                    <td style={{ padding: "0.75rem", borderBottom: "1px solid #334155" }}>
                      <Link to={`/admin/complaints/${encodeURIComponent(complaint.id)}`} style={{ color: "#38bdf8", whiteSpace: "nowrap" }}>
                        View details
                      </Link>
                    </td>
                  </tr>
                ))}
                {!complaints.length && !loading && (
                  <tr>
                    <td colSpan={8} style={{ padding: "2rem", color: "#cbd5e1", textAlign: "center" }}>
                      No complaints found matching the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {pageInfo.total > pageInfo.page_size && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", color: "#cbd5e1", marginBottom: "1rem" }}>
              <span>
                Showing {(pageInfo.page - 1) * pageInfo.page_size + 1}–{Math.min(pageInfo.page * pageInfo.page_size, pageInfo.total)} of {pageInfo.total}
              </span>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  disabled={pageInfo.page <= 1 || loading}
                  onClick={() => setPageInfo((current) => ({ ...current, page: current.page - 1 }))}
                  style={{ ...buttonStyle, background: "#334155" }}
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={pageInfo.page * pageInfo.page_size >= pageInfo.total || loading}
                  onClick={() => setPageInfo((current) => ({ ...current, page: current.page + 1 }))}
                  style={{ ...buttonStyle, background: "#334155" }}
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {complaints.length === 0 ? (
            <div style={{
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "0.75rem",
              padding: "3rem",
              textAlign: "center"
            }}>
              <div style={{ color: "#cbd5e1", fontSize: "1rem" }}>
                No complaints found matching the current filters
              </div>
            </div>
          ) : (
            <details style={{ marginTop: "1rem" }}>
              <summary style={{ color: "#cbd5e1", cursor: "pointer", marginBottom: "1rem" }}>
                Additional complaint actions and evidence
              </summary>
            {complaints.map((complaint) => (
              <div key={complaint.id} style={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "0.75rem",
                padding: "1.5rem",
                marginBottom: "1.5rem"
              }}>
                {/* Header */}
                <div style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  marginBottom: "1rem"
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.75rem",
                      marginBottom: "0.25rem"
                    }}>
                      ID: {complaint.id}
                    </div>
                    <div style={{
                      color: "#f8fafc",
                      fontSize: "1rem",
                      fontWeight: "600",
                      marginBottom: "0.5rem",
                      lineHeight: "1.4"
                    }}>
                      {complaint.text.length > 100 
                        ? complaint.text.substring(0, 100) + "..." 
                        : complaint.text}
                    </div>
                  </div>
                  <div style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: "0.5rem"
                  }}>
                    <div style={{
                      background: complaint.priority === "high" ? "#dc2626" : 
                                 complaint.priority === "medium" ? "#ea580c" : "#16a34a",
                      color: "white",
                      padding: "0.25rem 0.75rem",
                      borderRadius: "0.375rem",
                      fontSize: "0.75rem",
                      fontWeight: "600",
                      textTransform: "capitalize"
                    }}>
                      {complaint.priority}
                    </div>
                    <div style={{
                      background: complaint.status === "Pending" ? "#f59e0b" :
                                 complaint.status === "In Progress" ? "#3b82f6" : "#10b981",
                      color: "white",
                      padding: "0.25rem 0.75rem",
                      borderRadius: "0.375rem",
                      fontSize: "0.75rem",
                      fontWeight: "600"
                    }}>
                      {complaint.status}
                    </div>
                  </div>
                </div>

                {/* Image Preview */}
                {complaint.file_path && (
                  <div style={{ marginBottom: "1rem" }}>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.875rem",
                      marginBottom: "0.5rem"
                    }}>
                      Evidence
                    </div>
                    {complaint.file_path.match(/\.(jpg|jpeg|png|gif|bmp)$/i) ? (
                      <img
                        src={`http://127.0.0.1:8000/${complaint.file_path}`}
                        alt="Complaint evidence"
                        style={{
                          width: "100%",
                          maxHeight: "200px",
                          objectFit: "cover",
                          borderRadius: "0.5rem",
                          border: "1px solid #475569"
                        }}
                      />
                    ) : (
                      <video
                        src={`http://127.0.0.1:8000/${complaint.file_path}`}
                        controls
                        style={{
                          width: "100%",
                          maxHeight: "200px",
                          borderRadius: "0.5rem",
                          border: "1px solid #475569"
                        }}
                      />
                    )}
                  </div>
                )}

                {/* Details Grid */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                  gap: "1rem",
                  marginBottom: "1rem"
                }}>
                  <div>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.75rem",
                      marginBottom: "0.25rem"
                    }}>
                      Category
                    </div>
                    <div style={{
                      color: "#f8fafc",
                      fontWeight: "500",
                      textTransform: "capitalize"
                    }}>
                      {complaint.category}
                    </div>
                  </div>

                  <div>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.75rem",
                      marginBottom: "0.25rem"
                    }}>
                      Priority
                    </div>
                    <div style={{
                      color: complaint.priority === "high" ? "#dc2626" : 
                             complaint.priority === "medium" ? "#ea580c" : "#16a34a",
                      fontWeight: "500",
                      textTransform: "capitalize"
                    }}>
                      {complaint.priority}
                    </div>
                  </div>

                  <div>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.75rem",
                      marginBottom: "0.25rem"
                    }}>
                      Status
                    </div>
                    <div style={{
                      color: complaint.status === "Pending" ? "#f59e0b" :
                             complaint.status === "In Progress" ? "#3b82f6" : "#10b981",
                      fontWeight: "500"
                    }}>
                      {complaint.status}
                    </div>
                  </div>
                </div>

                {/* Location */}
                {complaint.latitude && complaint.longitude && (
                  <div style={{
                    background: "#0f172a",
                    padding: "0.75rem",
                    borderRadius: "0.5rem",
                    border: "1px solid #475569",
                    marginBottom: "1rem"
                  }}>
                    <div style={{
                      color: "#cbd5e1",
                      fontSize: "0.75rem",
                      marginBottom: "0.25rem"
                    }}>
                      Location
                    </div>
                    <div style={{
                      color: "#f8fafc",
                      fontSize: "0.875rem"
                    }}>
                      📍 {complaint.latitude.toFixed(4)}, {complaint.longitude.toFixed(4)}
                    </div>
                  </div>
                )}

                {/* Timestamp */}
                <div style={{
                  color: "#94a3b8",
                  fontSize: "0.75rem",
                  textAlign: "right",
                  marginBottom: "1rem"
                }}>
                  {new Date(complaint.timestamp).toLocaleString()}
                </div>

                {complaint.status === "Resolved" && complaint.resolution_date && (
                  <section style={{
                    background: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "0.5rem",
                    padding: "1rem",
                    marginBottom: "1rem",
                    color: "#cbd5e1",
                  }}>
                    <h4 style={{ color: "#f8fafc", margin: "0 0 0.5rem" }}>Approved resolution</h4>
                    <p>Resolution date: {complaint.resolution_date}</p>
                    {complaint.resolution_officer && <p>Submitted by: {complaint.resolution_officer}</p>}
                    {complaint.resolution_submitted_at && (
                      <p>Submitted on: {new Date(complaint.resolution_submitted_at).toLocaleString()}</p>
                    )}
                    {complaint.resolution_findings && <p><strong>Findings:</strong> {complaint.resolution_findings}</p>}
                    {complaint.resolution_remarks && <p><strong>Remarks:</strong> {complaint.resolution_remarks}</p>}
                    {complaint.resolution_attachment_url && (
                      <button
                        type="button"
                        onClick={() => downloadResolutionAttachment({
                          attachment_url: complaint.resolution_attachment_url,
                          attachment_name: complaint.resolution_attachment_name,
                        })}
                        style={{ ...buttonStyle, background: "#334155" }}
                      >
                        Download {complaint.resolution_attachment_name}
                      </button>
                    )}
                  </section>
                )}

                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  flexWrap: "wrap",
                  marginBottom: "1rem",
                  color: "#cbd5e1",
                  fontSize: "0.875rem",
                }}>
                  <span>
                    {complaint.assigned_officer
                      ? `Assigned to ${complaint.assigned_officer}${complaint.assigned_at ? ` on ${new Date(complaint.assigned_at).toLocaleString()}` : ""}`
                      : "Unassigned"}
                  </span>
                  <select
                    aria-label={`Assign complaint ${complaint.id}`}
                    value={selectedOfficers[complaint.id] ?? complaint.assigned_officer_id ?? ""}
                    onChange={(event) =>
                      setSelectedOfficers((current) => ({
                        ...current,
                        [complaint.id]: event.target.value,
                      }))
                    }
                    style={{
                      padding: "0.5rem",
                      background: "#0f172a",
                      border: "1px solid #475569",
                      borderRadius: "0.375rem",
                      color: "#f8fafc",
                    }}
                  >
                    <option value="">Select officer</option>
                    {officers.map((officer) => (
                      <option key={officer.id} value={officer.id}>
                        {officer.name}{officer.department ? ` — ${officer.department}` : ""} ({officer.email})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!officers.length || !selectedOfficers[complaint.id] || assigningId === complaint.id}
                    onClick={() => handleAssignOfficer(complaint.id)}
                    style={{
                      background: "#3b82f6",
                      color: "white",
                      border: "none",
                      padding: "0.5rem 0.75rem",
                      borderRadius: "0.375rem",
                      cursor: !officers.length || assigningId === complaint.id ? "not-allowed" : "pointer",
                    }}
                  >
                    {assigningId === complaint.id ? "Assigning..." : "Assign Officer"}
                  </button>
                </div>

                {complaint.status !== "Resolved" && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                    color: "#cbd5e1",
                  }}>
                    <label htmlFor={`status-${complaint.id}`}>Update status</label>
                    <select
                      id={`status-${complaint.id}`}
                      value={selectedStatuses[complaint.id] ?? complaint.status}
                      onChange={(event) => setSelectedStatuses((current) => ({
                        ...current,
                        [complaint.id]: event.target.value,
                      }))}
                      style={{
                        padding: "0.5rem",
                        background: "#0f172a",
                        border: "1px solid #475569",
                        borderRadius: "0.375rem",
                        color: "#f8fafc",
                      }}
                    >
                      <option value="Pending">Pending</option>
                      <option value="In Progress">In Progress</option>
                    </select>
                    <button
                      type="button"
                      disabled={
                        updatingStatusId === complaint.id ||
                        (selectedStatuses[complaint.id] ?? complaint.status) === complaint.status
                      }
                      onClick={() => handleUpdateStatus(complaint)}
                      style={{
                        ...buttonStyle,
                        background: "#3b82f6",
                        cursor: updatingStatusId === complaint.id ? "not-allowed" : "pointer",
                      }}
                    >
                      {updatingStatusId === complaint.id ? "Updating..." : "Update status"}
                    </button>
                    <span style={{ color: "#94a3b8", fontSize: "0.875rem" }}>
                      Resolved status is applied through resolution review.
                    </span>
                  </div>
                )}
              </div>
            ))}
            </details>
          )}
        </div>
      </div>
    </div>
  );
}