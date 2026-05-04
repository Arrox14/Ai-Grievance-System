import { useState, useRef } from "react";
import axios from "axios";

export default function Upload() {
  const [complaintText, setComplaintText] = useState("");
  const [file, setFile] = useState(null);
  const [location, setLocation] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [preview, setPreview] = useState(null);
  const [stream, setStream] = useState(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [submissionResult, setSubmissionResult] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const getLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLocation({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude
          });
        },
        (error) => {
          console.error("Error getting location:", error);
          alert("Unable to get your location. Please enable location services.");
        }
      );
    } else {
      alert("Geolocation is not supported by your browser.");
    }
  };

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: "environment" } 
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      setIsCameraActive(true);
    } catch (error) {
      console.error("Error accessing camera:", error);
      alert("Unable to access camera. Please check permissions.");
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
      setIsCameraActive(false);
    }
  };

  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0);
      
      canvas.toBlob((blob) => {
        const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
        setFile(file);
        setPreview(URL.createObjectURL(file));
        stopCamera();
      }, "image/jpeg");
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      if (selectedFile.type.startsWith("image/")) {
        setPreview(URL.createObjectURL(selectedFile));
      } else {
        setPreview(null);
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!complaintText.trim()) {
      alert("Please enter complaint text");
      return;
    }

    setIsSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("text", complaintText);
      if (file) {
        formData.append("file", file);
      }
      if (location) {
        formData.append("latitude", location.latitude);
        formData.append("longitude", location.longitude);
      }

      const response = await axios.post(
        "http://127.0.0.1:8000/submit-complaint", 
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      );

      // Store submission result to display
      setSubmissionResult(response.data);
      
      // Reset form
      setComplaintText("");
      setFile(null);
      setPreview(null);
      setLocation(null);
      
    } catch (error) {
      console.error("Error submitting complaint:", error);
      alert("Failed to submit complaint. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      minHeight: "calc(100vh - 80px)",
      background: "#0f172a",
      padding: "2rem"
    }}>
      <div style={{
        maxWidth: "800px",
        margin: "0 auto"
      }}>
        <h1 style={{
          color: "#f8fafc",
          fontSize: "2rem",
          fontWeight: "bold",
          marginBottom: "2rem",
          textAlign: "center"
        }}>
          Submit Complaint
        </h1>

        <form onSubmit={handleSubmit} style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "0.75rem",
          padding: "2rem"
        }}>
          {/* Complaint Text */}
          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{
              display: "block",
              color: "#f8fafc",
              fontWeight: "500",
              marginBottom: "0.5rem"
            }}>
              Complaint Description *
            </label>
            <textarea
              value={complaintText}
              onChange={(e) => setComplaintText(e.target.value)}
              placeholder="Describe your complaint in detail..."
              required
              style={{
                width: "100%",
                minHeight: "120px",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "0.5rem",
                color: "#f8fafc",
                fontSize: "1rem",
                resize: "vertical",
                fontFamily: "inherit"
              }}
            />
          </div>

          {/* File Upload */}
          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{
              display: "block",
              color: "#f8fafc",
              fontWeight: "500",
              marginBottom: "0.5rem"
            }}>
              Upload Evidence (Image/Video)
            </label>
            <input
              type="file"
              accept="image/*,video/*"
              onChange={handleFileChange}
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "0.5rem",
                color: "#f8fafc",
                fontSize: "1rem"
              }}
            />
          </div>

          {/* Camera Capture */}
          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{
              display: "block",
              color: "#f8fafc",
              fontWeight: "500",
              marginBottom: "0.5rem"
            }}>
              Or Capture Photo
            </label>
            <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
              <button
                type="button"
                onClick={isCameraActive ? stopCamera : startCamera}
                style={{
                  background: isCameraActive ? "#ef4444" : "#3b82f6",
                  color: "white",
                  border: "none",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "0.5rem",
                  cursor: "pointer",
                  fontWeight: "500",
                  transition: "background 0.2s"
                }}
              >
                {isCameraActive ? "Stop Camera" : "Start Camera"}
              </button>
              {isCameraActive && (
                <button
                  type="button"
                  onClick={capturePhoto}
                  style={{
                    background: "#10b981",
                    color: "white",
                    border: "none",
                    padding: "0.75rem 1.5rem",
                    borderRadius: "0.5rem",
                    cursor: "pointer",
                    fontWeight: "500",
                    transition: "background 0.2s"
                  }}
                >
                  Capture Photo
                </button>
              )}
            </div>
            
            {isCameraActive && (
              <div style={{ marginBottom: "1rem" }}>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  style={{
                    width: "100%",
                    maxWidth: "400px",
                    borderRadius: "0.5rem",
                    border: "1px solid #475569"
                  }}
                />
                <canvas ref={canvasRef} style={{ display: "none" }} />
              </div>
            )}
          </div>

          {/* Preview */}
          {preview && (
            <div style={{ marginBottom: "1.5rem" }}>
              <label style={{
                display: "block",
                color: "#f8fafc",
                fontWeight: "500",
                marginBottom: "0.5rem"
              }}>
                Preview
              </label>
              <img
                src={preview}
                alt="Preview"
                style={{
                  maxWidth: "300px",
                  maxHeight: "200px",
                  borderRadius: "0.5rem",
                  border: "1px solid #475569"
                }}
              />
            </div>
          )}

          {/* Location */}
          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{
              display: "block",
              color: "#f8fafc",
              fontWeight: "500",
              marginBottom: "0.5rem"
            }}>
              Location
            </label>
            <button
              type="button"
              onClick={getLocation}
              style={{
                background: "#f59e0b",
                color: "white",
                border: "none",
                padding: "0.75rem 1.5rem",
                borderRadius: "0.5rem",
                cursor: "pointer",
                fontWeight: "500",
                transition: "background 0.2s"
              }}
            >
              Get My Location
            </button>
            
            {location && (
              <div style={{
                marginTop: "0.75rem",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "0.5rem",
                color: "#cbd5e1"
              }}>
                <strong>Location captured:</strong><br />
                Latitude: {location.latitude.toFixed(6)}<br />
                Longitude: {location.longitude.toFixed(6)}
              </div>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              width: "100%",
              background: isSubmitting ? "#64748b" : "#3b82f6",
              color: "white",
              border: "none",
              padding: "1rem",
              borderRadius: "0.5rem",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              transition: "background 0.2s"
            }}
          >
            {isSubmitting ? "Submitting..." : "Submit Complaint"}
          </button>
        </form>

        {/* Submission Result */}
        {submissionResult && (
          <div style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "2rem",
            marginTop: "2rem"
          }}>
            <h3 style={{
              color: "#10b981",
              margin: "0 0 1rem 0",
              fontSize: "1.25rem",
              fontWeight: "600"
            }}>
              Complaint Submitted Successfully!
            </h3>
            
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1rem",
              marginBottom: "1.5rem"
            }}>
              <div style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569"
              }}>
                <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  Complaint ID
                </div>
                <div style={{ color: "#f8fafc", fontWeight: "600" }}>
                  {submissionResult.id}
                </div>
              </div>
              
              <div style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569"
              }}>
                <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  Category
                </div>
                <div style={{ 
                  color: "#f8fafc", 
                  fontWeight: "600",
                  textTransform: "capitalize"
                }}>
                  {submissionResult.category}
                </div>
              </div>
              
              <div style={{
                background: "#0f172a",
                padding: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #475569"
              }}>
                <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.25rem" }}>
                  Priority
                </div>
                <div style={{ 
                  color: submissionResult.priority === "high" ? "#dc2626" : 
                         submissionResult.priority === "medium" ? "#ea580c" : "#16a34a",
                  fontWeight: "600",
                  textTransform: "capitalize"
                }}>
                  {submissionResult.priority}
                </div>
              </div>
            </div>

            <div style={{
              background: "#0f172a",
              padding: "1rem",
              borderRadius: "0.5rem",
              border: "1px solid #475569"
            }}>
              <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                Status
              </div>
              <div style={{ 
                color: "#f8fafc", 
                fontWeight: "600"
              }}>
                {submissionResult.status}
              </div>
            </div>

            <div style={{
              marginTop: "1rem",
              padding: "1rem",
              background: "#0f172a",
              borderRadius: "0.5rem",
              border: "1px solid #475569"
            }}>
              <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                Timestamp
              </div>
              <div style={{ color: "#f8fafc" }}>
                {new Date(submissionResult.timestamp).toLocaleString()}
              </div>
            </div>

            {submissionResult.file_path && (
              <div style={{
                marginTop: "1rem",
                padding: "1rem",
                background: "#0f172a",
                borderRadius: "0.5rem",
                border: "1px solid #475569"
              }}>
                <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                  Evidence File
                </div>
                <div style={{ color: "#f8fafc", fontSize: "0.875rem" }}>
                  {submissionResult.file_path}
                </div>
              </div>
            )}

            {submissionResult.latitude && submissionResult.longitude && (
              <div style={{
                marginTop: "1rem",
                padding: "1rem",
                background: "#0f172a",
                borderRadius: "0.5rem",
                border: "1px solid #475569"
              }}>
                <div style={{ color: "#cbd5e1", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                  Location
                </div>
                <div style={{ color: "#f8fafc", fontSize: "0.875rem" }}>
                  Lat: {submissionResult.latitude.toFixed(6)}, Lon: {submissionResult.longitude.toFixed(6)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}