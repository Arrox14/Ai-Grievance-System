export default function ComplaintCard({ complaint, onUpdateStatus, updatingId }) {
  const getPriorityColor = (priority) => {
    switch (priority.toLowerCase()) {
      case 'high':
        return '#dc2626';
      case 'medium':
        return '#ea580c';
      case 'low':
        return '#16a34a';
      default:
        return '#6b7280';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'Pending':
        return '#f59e0b';
      case 'In Progress':
        return '#3b82f6';
      case 'Resolved':
        return '#10b981';
      default:
        return '#6b7280';
    }
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div style={{
      background: '#1e293b',
      border: '1px solid #334155',
      borderRadius: '0.5rem',
      padding: '1.5rem',
      marginBottom: '1rem',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      transition: 'transform 0.2s, box-shadow 0.2s'
    }}
    onMouseOver={(e) => {
      e.currentTarget.style.transform = 'translateY(-2px)';
      e.currentTarget.style.boxShadow = '0 8px 12px rgba(0, 0, 0, 0.15)';
    }}
    onMouseOut={(e) => {
      e.currentTarget.style.transform = 'translateY(0)';
      e.currentTarget.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
    }}
    >
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '1rem'
      }}>
        <div>
          <h3 style={{
            color: '#f8fafc',
            margin: '0 0 0.5rem 0',
            fontSize: '1.125rem',
            fontWeight: '600'
          }}>
            Complaint ID: {complaint.id.slice(0, 8)}...
          </h3>
          <p style={{
            color: '#cbd5e1',
            margin: '0',
            lineHeight: '1.5'
          }}>
            {complaint.text}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span style={{
            background: getPriorityColor(complaint.priority),
            color: 'white',
            padding: '0.25rem 0.75rem',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            fontWeight: '600',
            textTransform: 'uppercase'
          }}>
            {complaint.priority}
          </span>
          <span style={{
            background: getStatusColor(complaint.status),
            color: 'white',
            padding: '0.25rem 0.75rem',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            fontWeight: '600'
          }}>
            {complaint.status}
          </span>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        marginBottom: '1rem'
      }}>
        <div>
          <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Category:</span>
          <p style={{ color: '#f8fafc', margin: '0.25rem 0 0 0', fontWeight: '500' }}>
            {complaint.category}
          </p>
        </div>
        <div>
          <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Timestamp:</span>
          <p style={{ color: '#f8fafc', margin: '0.25rem 0 0 0', fontWeight: '500' }}>
            {formatDate(complaint.timestamp)}
          </p>
        </div>
        {complaint.latitude && complaint.longitude && (
          <div>
            <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Location:</span>
            <p style={{ color: '#f8fafc', margin: '0.25rem 0 0 0', fontWeight: '500' }}>
              {complaint.latitude.toFixed(4)}, {complaint.longitude.toFixed(4)}
            </p>
          </div>
        )}
      </div>

      {complaint.file_path && (
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Evidence:</span>
          <div style={{ marginTop: '0.5rem' }}>
            {complaint.file_path.match(/\.(jpg|jpeg|png|gif|bmp)$/i) ? (
              <img
                src={`http://127.0.0.1:8000/${complaint.file_path}`}
                alt="Complaint evidence"
                style={{
                  maxWidth: '200px',
                  maxHeight: '150px',
                  borderRadius: '0.375rem',
                  border: '1px solid #475569'
                }}
              />
            ) : (
              <video
                src={`http://127.0.0.1:8000/${complaint.file_path}`}
                controls
                style={{
                  maxWidth: '200px',
                  maxHeight: '150px',
                  borderRadius: '0.375rem',
                  border: '1px solid #475569'
                }}
              />
            )}
          </div>
        </div>
      )}

      {onUpdateStatus && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Update Status:</span>
          <select
            value={complaint.status}
            onChange={(e) => onUpdateStatus(complaint.id, e.target.value)}
            disabled={updatingId === complaint.id}
            style={{
              background: "#0f172a",
              color: "#f8fafc",
              border: "1px solid #475569",
              padding: "0.375rem 0.75rem",
              borderRadius: "0.375rem",
              fontSize: "0.875rem",
              opacity: updatingId === complaint.id ? 0.6 : 1,
              cursor: updatingId === complaint.id ? "not-allowed" : "pointer"
            }}
          >
            <option value="Pending">Pending</option>
            <option value="In Progress">In Progress</option>
            <option value="Resolved">Resolved</option>
          </select>
          {updatingId === complaint.id && (
            <span style={{ color: "#3b82f6", fontSize: "0.875rem", marginLeft: "0.5rem" }}>
              Updating...
            </span>
          )}
        </div>
      )}
    </div>
  );
}
