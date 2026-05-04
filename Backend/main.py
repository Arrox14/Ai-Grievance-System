from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pickle
import os
import sqlite3
from datetime import datetime
import uuid
import cv2
import numpy as np
from ultralytics import YOLO

app = FastAPI(title="Public Grievance Intelligence System API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DATABASE_DIR = os.path.join(BASE_DIR, "database")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)

# Database initialization
def init_db():
    db_path = os.path.join(BASE_DIR, "complaints.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            file TEXT,
            lat REAL,
            lon REAL,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Load ML models
try:
    model_category = pickle.load(open(os.path.join(BASE_DIR, "category_model.pkl"), "rb"))
    model_priority = pickle.load(open(os.path.join(BASE_DIR, "priority_model.pkl"), "rb"))
    vectorizer = pickle.load(open(os.path.join(BASE_DIR, "vectorizer.pkl"), "rb"))
    le_category = pickle.load(open(os.path.join(BASE_DIR, "le_category.pkl"), "rb"))
    le_priority = pickle.load(open(os.path.join(BASE_DIR, "le_priority.pkl"), "rb"))
    # Load YOLO model
    yolo_model = YOLO(os.path.join(BASE_DIR, 'yolov8n.pt'))
except Exception as e:
    print(f"Error loading models: {e}")
    model_category = None
    model_priority = None
    vectorizer = None
    le_category = None
    le_priority = None
    yolo_model = None

# YOLOv8 object detection function
def detect_objects(path):
    """
    Use ultralytics YOLOv8 to detect objects in an image or video file
    Returns detected object names
    """
    if not yolo_model:
        return []
    
    try:
        # Process image
        if path.lower().endswith(('.mp4', '.avi', '.mov')):
            # For video, extract first frame
            cap = cv2.VideoCapture(path)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return []
            image = frame
        else:
            # For image
            image = cv2.imread(path)
        
        if image is None:
            return []
        
        # Run YOLO detection
        results = yolo_model(image)
        detected_objects = []
        
        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                if confidence > 0.5:  # Filter by confidence
                    detected_objects.append(class_name)
        
        return list(set(detected_objects))  # Return unique objects
    except Exception as e:
        print(f"Error in object detection: {e}")
        return []

# Pydantic models
class ComplaintRequest(BaseModel):
    text: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ComplaintResponse(BaseModel):
    id: str
    text: str
    category: str
    priority: str
    file_path: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    timestamp: str
    status: str

class StatusUpdate(BaseModel):
    status: str

# Routes
@app.get("/")
def home():
    return {"message": "AI Grievance System Running", "version": "1.0.0"}

@app.post("/predict")
def predict(text: str):
    if not all([model_category, model_priority, vectorizer, le_category, le_priority]):
        raise HTTPException(status_code=500, detail="ML models not loaded")
    
    vec = vectorizer.transform([text])
    category = le_category.inverse_transform(model_category.predict(vec))[0]
    priority = le_priority.inverse_transform(model_priority.predict(vec))[0]
    
    return {"category": category, "priority": priority}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp4', '.avi', '.mov']
    
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not supported")
    
    file_path = os.path.join(UPLOADS_DIR, f"{uuid.uuid4()}{file_extension}")
    
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.post("/analyze-image")
async def analyze_image(file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    if not yolo_model:
        raise HTTPException(status_code=500, detail="YOLO model not loaded")
    
    try:
        # Process image
        if file_path.lower().endswith(('.mp4', '.avi', '.mov')):
            # For video, extract first frame
            cap = cv2.VideoCapture(file_path)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                raise HTTPException(status_code=400, detail="Could not read video file")
            image = frame
        else:
            # For image
            image = cv2.imread(file_path)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Could not read image file")
        
        # Run YOLO detection
        results = yolo_model(image)
        detected_objects = []
        
        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                detected_objects.append({
                    "object": class_name,
                    "confidence": confidence
                })
        
        return {
            "detected_objects": detected_objects,
            "total_objects": len(detected_objects)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/submit-complaint", response_model=ComplaintResponse)
async def submit_complaint(
    text: str = Form(...),
    file: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None)
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Complaint text is required")
    
    # Get prediction from existing NLP model
    if not all([model_category, model_priority, vectorizer, le_category, le_priority]):
        raise HTTPException(status_code=500, detail="ML models not loaded")
    
    vec = vectorizer.transform([text])
    category = le_category.inverse_transform(model_category.predict(vec))[0]
    priority = le_priority.inverse_transform(model_priority.predict(vec))[0]
    
    # Handle file upload and run YOLO detection
    file_path = None
    detected_objects = []
    if file and file.filename:
        upload_result = await upload(file)
        file_path = upload_result["file_path"]
        # Run YOLOv8 detection on uploaded file
        detected_objects = detect_objects(file_path)
    
    # Generate timestamp
    timestamp = datetime.now().isoformat()
    
    # Store in database using new schema
    db_path = os.path.join(BASE_DIR, "complaints.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO complaints 
        (text, category, priority, file, lat, lon, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (text, category, priority, file_path, latitude, longitude, "Pending", timestamp))
    conn.commit()
    
    # Get the auto-incremented ID
    complaint_id = cursor.lastrowid
    conn.close()
    
    return ComplaintResponse(
        id=str(complaint_id),
        text=text,
        category=category,
        priority=priority,
        file_path=file_path,
        latitude=latitude,
        longitude=longitude,
        timestamp=timestamp,
        status="Pending"
    )

@app.get("/complaints", response_model=List[ComplaintResponse])
def get_complaints():
    db_path = os.path.join(BASE_DIR, "complaints.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    complaints = []
    for row in rows:
        complaints.append(ComplaintResponse(
            id=str(row[0]),
            text=row[1],
            category=row[2],
            priority=row[3],
            file_path=row[4],
            latitude=row[5],
            longitude=row[6],
            timestamp=row[7],
            status=row[8]
        ))
    
    return complaints

@app.put("/update-status/{complaint_id}")
def update_status(complaint_id: str, status_update: StatusUpdate):
    valid_statuses = ["Pending", "In Progress", "Resolved"]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    db_path = os.path.join(BASE_DIR, "complaints.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (status_update.status, complaint_id))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    conn.commit()
    conn.close()
    
    return {"message": "Status updated successfully", "complaint_id": complaint_id, "new_status": status_update.status}

@app.get("/complaints/filter", response_model=List[ComplaintResponse])
def filter_complaints(category: Optional[str] = None, priority: Optional[str] = None):
    db_path = os.path.join(BASE_DIR, "complaints.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    complaints = []
    for row in rows:
        complaints.append(ComplaintResponse(
            id=str(row[0]),
            text=row[1],
            category=row[2],
            priority=row[3],
            file_path=row[4],
            latitude=row[5],
            longitude=row[6],
            timestamp=row[7],
            status=row[8]
        ))
    
    return complaints