# Public Grievance Intelligence System (PGIS)

A production-level AI-powered Public Grievance Intelligence System built with React (Vite) frontend and FastAPI backend, featuring NLP-based complaint classification and YOLOv8 image analysis.

## Features

- **AI-Powered Classification**: Automatic categorization and priority assignment using TF-IDF + SVM
- **Image Analysis**: YOLOv8-powered object detection for uploaded evidence
- **Location Tracking**: GPS coordinates for precise complaint location
- **Real-time Status Updates**: Live tracking of complaint resolution progress
- **Professional Dashboard**: Government-style dark theme interface
- **Admin Panel**: Comprehensive complaint management system

## Tech Stack

### Frontend
- **React** with Vite
- **React Router** for navigation
- **Axios** for API calls
- **Professional Dark Theme** with government-style design

### Backend
- **FastAPI** (Python)
- **SQLite** database
- **TF-IDF + SVM** for NLP classification
- **YOLOv8** for image object detection
- **OpenCV** for image processing

## Project Structure

```
AI-Grievance-System/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   ├── uploads/               # File upload directory
│   ├── database/              # SQLite database
│   └── *.pkl                 # Trained ML models
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   └── ComplaintCard.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Upload.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── Admin.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Start the FastAPI server:
```bash
python main.py
```

Authentication requires a stable `JWT_SECRET` of at least 32 characters. The
backend reads a local `Backend/.env` file on startup without overriding
environment variables already supplied by the process. For local development,
create the file once in PowerShell:

```powershell
Set-Location "C:\CollegeProjects\Ai-Grievance-System - Copy\Backend"
"JWT_SECRET=$((python -c 'import secrets; print(secrets.token_urlsafe(48))').Trim())" |
  Set-Content -Encoding ascii .env
python -m uvicorn main:app --reload
```

The `.env` file is ignored by Git. Keep its value stable across backend
restarts; changing it invalidates existing login tokens. For deployments, set
`JWT_SECRET` in the deployment environment instead.

### Versioned SQLite schema migration

The API checks the schema version at startup and does not silently change the
database. Stop the backend before applying a migration. From PowerShell, run
the versioned command from `Backend`:

```powershell
Set-Location "C:\CollegeProjects\Ai-Grievance-System - Copy\Backend"
.\venv\Scripts\python.exe -m app.migrations `
  --database .\complaints.db `
  --backup ".\backups\complaints.pre-migration-$((Get-Date).ToString('yyyyMMdd-HHmmss')).sqlite3"
```

The command verifies a SQLite backup before applying the migration in a
transaction. It refuses to overwrite an existing backup. Version 1 reuses the
existing `users`, current complaint assignment fields, status history and
notifications; it adds departments, officer profiles, assignment history and
AI analysis results. Version 2 adds notification types and permits notifications
that are not tied to a complaint, while preserving all existing notification
IDs and values. It also adds optional error details to AI analysis records.
Existing officer accounts receive an otherwise empty profile with no inferred
department. Existing complaints, IDs, timestamps, ownership and file paths are
preserved. No assignment or status history and no AI results are fabricated for
past complaints; prior reassignment details that were never recorded cannot be
reconstructed. New text-classification results are recorded for newly submitted
complaints.

The migration tests can be run without modifying the project database:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_migrations.py" -v
```

The backend will be running at `http://localhost:8000`

The trained model artifacts are not included in this checkout. Until
`category_model.pkl`, `priority_model.pkl`, `vectorizer.pkl`, `le_category.pkl`,
and `le_priority.pkl` are supplied in `Backend`, `POST /predict` and
`POST /submit-complaint` return HTTP 500 with `ML models not loaded`. The
`yolov8n.pt` weights are also required for image detection; without them,
`POST /analyze-image` returns HTTP 503 with `YOLO model not loaded`. Missing
artifacts do not prevent the API from starting, and the backend does not
download substitute weights or classifier models.

### First Administrator Setup (Windows)

To create the first administrator, stop any backend already using port 8000
and ensure the local `.env` file or process environment contains `JWT_SECRET`.
From the `Backend` directory run:

```powershell
python run_admin_setup.py
```

This starts the API with a temporary, one-time bootstrap token and prints that
token in the terminal. Keep the terminal open, open `/admin-setup` in the
frontend, and enter the printed token. This setup command is only for the first
administrator; once the account is created, preserve the same `JWT_SECRET`,
stop this server, and start the backend normally.

On startup, the backend adds a `token_version` column to the existing `users`
table if it is missing. The additive migration gives existing rows a value of
zero and leaves existing complaint records unchanged. Logging out increments
that value to invalidate the user's existing JWTs.

### Reset an Existing Administrator Password (Windows)

If the existing administrator's password is unknown, stop the backend and run
this from the `Backend` directory. The utility prompts for the administrator
email and new password without echoing the password, only updates an existing
admin account in `complaints.db`, and invalidates that account's current tokens.
It does not create an admin or change account roles.

```powershell
python reset_admin_password.py
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be running at `http://localhost:5173`

## API Endpoints

### Core Endpoints

- `GET /` - Health check
- `POST /predict` - Predict category and priority from text
- `POST /upload` - Upload image/video files
- `POST /analyze-image` - Analyze an owned image with YOLOv8
- `POST /live-detect` - Analyze one authenticated browser-camera JPEG frame (maximum 512 KB and 640x480); frames and annotations are returned in memory and are not stored
- `GET /analysis-images/annotated` - Download your annotated analysis image
- `POST /submit-complaint` - Submit a new complaint

### Management Endpoints

- `GET /complaints` - Get all complaints
- `GET /complaints/filter` - Filter complaints by category/priority
- `GET /admin/complaint-filter-options` - Return existing complaint categories, active departments, officers and supported status/priority values
- `GET /admin/complaints` - Search/filter/sort and paginate admin complaint results (`search`, `status`, `priority`, `category`, `date_from`, `date_to`, `department_id`, `officer_id`, `sort`, `page`, `page_size`)
- `GET /admin/complaints/{complaint_id}` - Get admin complaint details, existing status/assignment history, and resolution information
- `GET /admin/complaints/{complaint_id}/evidence` - Download evidence after administrator authorization
- `PUT /update-status/{id}` - Update complaint status

## Database Schema

```sql
CREATE TABLE complaints (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    file_path TEXT,
    latitude REAL,
    longitude REAL,
    timestamp TEXT NOT NULL,
    status TEXT DEFAULT 'Pending'
);
```

## Usage

### Submitting a Complaint

1. Navigate to the Upload page
2. Enter complaint description
3. Upload image/video evidence (optional)
4. Capture photo using camera (optional)
5. Get GPS location (optional)
6. Submit complaint

### Viewing Complaints

1. **Dashboard Page**: View all complaints with filtering options
2. **Admin Panel**: Manage complaints and update status

### AI Features

- **Text Classification**: Automatically categorizes complaints into:
  - Water
  - Electricity
  - Road
  - Sanitation
  - Waste Management
  - Other

- **Priority Assignment**: Automatically assigns priority levels:
  - High
  - Medium
  - Low

- **Image Analysis**: Detects multiple objects in uploaded images using YOLOv8

## Configuration

### ML Models

The system uses pre-trained models:
- `category_model.pkl` - Text category classification
- `priority_model.pkl` - Priority classification
- `vectorizer.pkl` - TF-IDF vectorizer
- `le_category.pkl` - Category label encoder
- `le_priority.pkl` - Priority label encoder

### YOLOv8

Place compatible YOLOv8 weights at `Backend\yolov8n.pt`; the model is loaded
once when the backend process starts. The backend does not download weights.
`POST /analyze-image` accepts an owned image `file_path` and optional
`confidence` (0.05–0.95, default 0.5) and `iou` (0.1–0.95, default 0.45)
thresholds. It returns detections with class IDs/names, confidence and pixel
bounding boxes, image dimensions, and a private annotated-image download
reference. Only the authenticated upload owner can retrieve that annotated
image. Annotated files are stored under `Backend\data\uploads\annotated` with
generated UUID filenames. When the source file is attached to one of the
authenticated citizen's complaints, the detection metadata is recorded as a
new `image_object_detection` entry in `ai_analysis_results`; the stored model
version identifies the installed Ultralytics runtime. The existing history
table requires a complaint ID, so analyses of standalone uploads are returned
to the caller but are not persisted in complaint analysis history.
`POST /analyze-video` separately accepts an owned video path, confidence/IoU
thresholds, a frame sampling interval (1–600 frames), and flags for timestamped
detections and optional annotated video output. Processing is synchronous and
limited to 10 MB, 120 seconds, 18,000 decoded frames, and 600 sampled frames.
Annotated videos are stored under
`Backend\data\uploads\annotated\videos` and retrieved through the owner-checked
`/analysis-videos/annotated/{video_id}` endpoint.

## Development

### Adding New Features

1. **Backend**: Add new endpoints in `main.py`
2. **Frontend**: Create new components in `src/components/`
3. **Pages**: Add new pages in `src/pages/`
4. **Styling**: Use inline styles with the dark theme color palette

### Color Scheme

- **Primary Background**: `#0f172a`
- **Secondary Background**: `#1e293b`
- **Border**: `#334155`
- **Text Primary**: `#f8fafc`
- **Text Secondary**: `#cbd5e1`
- **Text Muted**: `#94a3b8`
- **Primary Blue**: `#3b82f6`
- **Success Green**: `#10b981`
- **Warning Orange**: `#f59e0b`
- **Error Red**: `#ef4444`

## Production Deployment

### Backend

1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables
3. Use a production ASGI server like Gunicorn with Uvicorn
4. Set up reverse proxy with Nginx

### Frontend

1. Build the production bundle:
```bash
npm run build
```

2. Serve static files using a web server like Nginx

## Security Considerations

- File upload validation
- CORS configuration
- Input sanitization
- Rate limiting
- Authentication (to be added)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the repository.

---

**Note**: This is a demonstration system. For production use, ensure proper security measures, database scaling, and monitoring are implemented.
