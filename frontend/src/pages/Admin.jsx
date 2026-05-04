import { useState, useEffect } from "react";
import axios from "axios";
import ComplaintCard from "../components/ComplaintCard";

export default function Admin() {
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    category: "",
    priority: "",
    status: ""
  });
  const [updatingId, setUpdatingId] = useState(null);

  useEffect(() => {
    fetchComplaints();
  }, []);

  const fetchComplaints = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filter.category) params.append("category", filter.category);
      if (filter.priority) params.append("priority", filter.priority);
      
      const response = await axios.get(
        `http://127.0.0.1:8000/complaints${params.toString() ? '?' + params.toString() : ''}`
      );
      
      // Apply status filter on frontend since backend doesn't support it
      let filteredComplaints = response.data;
      if (filter.status) {
        filteredComplaints = response.data.filter(c => c.status === filter.status);
      }
      
      setComplaints(filteredComplaints);
    } catch (error) {
      console.error("Error fetching complaints:", error);
      alert("Failed to fetch complaints. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilter(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    fetchComplaints();
  };

  const clearFilters = () => {
    setFilter({ category: "", priority: "", status: "" });
    setTimeout(fetchComplaints, 0);
  };

  const handleStatusUpdate = async (complaintId, newStatus) => {
    try {
      setUpdatingId(complaintId);
      await axios.put(
        `http://127.0.0.1:8000/update-status/${complaintId}`,
        { status: newStatus }
      );
      
      // Update local state
      setComplaints(prev => 
        prev.map(complaint => 
          complaint.id === complaintId 
            ? { ...complaint, status: newStatus }
            : complaint
        )
      );
      
      alert("Status updated successfully");
    } catch (error) {
      console.error("Error updating status:", error);
      alert("Failed to update status. Please try again.");
    } finally {
      setUpdatingId(null);
    }
  };

  const getComplaintStats = () => {
    const stats = {
      total: complaints.length,
      pending: complaints.filter(c => c.status === "Pending").length,
      inProgress: complaints.filter(c => c.status === "In Progress").length,
      resolved: complaints.filter(c => c.status === "Resolved").length,
      high: complaints.filter(c => c.priority === "high").length,
      medium: complaints.filter(c => c.priority === "medium").length,
      low: complaints.filter(c => c.priority === "low").length
    };
    return stats;
  };

  const stats = getComplaintStats();

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
                <option value="water">Water</option>
                <option value="electricity">Electricity</option>
                <option value="road">Road</option>
                <option value="sanitation">Sanitation</option>
                <option value="waste">Waste Management</option>
                <option value="other">Other</option>
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
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
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
            Manage Complaints ({complaints.length})
          </h3>

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
            complaints.map((complaint) => (
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

                {/* Action Buttons */}
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {complaint.status !== "Resolved" && (
                    <button
                      onClick={() => handleStatusUpdate(complaint.id, "Resolved")}
                      disabled={updatingId === complaint.id}
                      style={{
                        background: updatingId === complaint.id ? "#64748b" : "#10b981",
                        color: "white",
                        border: "none",
                        padding: "0.5rem 1rem",
                        borderRadius: "0.375rem",
                        cursor: updatingId === complaint.id ? "not-allowed" : "pointer",
                        fontWeight: "500",
                        fontSize: "0.875rem"
                      }}
                    >
                      {updatingId === complaint.id ? "Updating..." : "Mark as Resolved"}
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}