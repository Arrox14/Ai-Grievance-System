# Public Grievance Intelligence System (PGIS)

A production-level AI-powered Public Grievance Intelligence System built with React (Vite) frontend and FastAPI backend, featuring NLP-based complaint classification and YOLOv8 image/video analysis.

## Features

- **AI-Powered Classification**: Automatic categorization and priority assignment using TF-IDF + SVM
- **Image/Video Analysis**: YOLOv8 powered object detection for uploaded evidence
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
- **YOLOv8** for image/video object detection
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

The backend will be running at `http://localhost:8000`

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
- `POST /analyze-image` - Analyze uploaded images with YOLOv8
- `POST /submit-complaint` - Submit a new complaint

### Management Endpoints

- `GET /complaints` - Get all complaints
- `GET /complaints/filter` - Filter complaints by category/priority
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

- **Image Analysis**: Detects objects in uploaded images/videos using YOLOv8

## Configuration

### ML Models

The system uses pre-trained models:
- `category_model.pkl` - Text category classification
- `priority_model.pkl` - Priority classification
- `vectorizer.pkl` - TF-IDF vectorizer
- `le_category.pkl` - Category label encoder
- `le_priority.pkl` - Priority label encoder

### YOLOv8

The system automatically downloads the YOLOv8n model on first run for object detection.

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
