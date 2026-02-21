# Document Upload API

A production-ready Python API for uploading documents to Google Cloud Storage. Documents are organized by user ID within the `documents.in` folder structure.

## Features

- Upload documents to Google Cloud Storage
- Automatic folder organization by user ID (`documents.in/{user_id}/`)
- Returns public URLs with full access rights
- Client authentication using clientId and secret (stored in PostgreSQL)
- Modular, clean architecture
- Comprehensive error handling and logging
- Environment-based configuration

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Google Cloud Storage bucket
- Google Cloud Service Account with Storage Admin permissions
- Service account JSON key file

## Setup

### 1. Clone and Navigate to Project

```bash
cd /Users/sajad/Documents/projects/dcumently
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

API_HOST=0.0.0.0
API_PORT=8000

DATABASE_URL=postgresql://username:password@localhost:5432/dcumently_db
```

### 5. Database Setup

1. Create a PostgreSQL database:
```bash
createdb dcumently_db
```

2. The database tables will be automatically created on application startup, or you can manually initialize them:
```bash
python -m app.scripts.init_db
```

3. Create client credentials for API authentication:
```bash
python -m app.scripts.manage_clients create <client_id> <client_secret>
```

Example:
```bash
python -m app.scripts.manage_clients create my_client_id my_secret_key
```

**Client Management Commands:**
- List all clients: `python -m app.scripts.manage_clients list`
- Activate a client: `python -m app.scripts.manage_clients activate <client_id>`
- Deactivate a client: `python -m app.scripts.manage_clients deactivate <client_id>`
- Delete a client: `python -m app.scripts.manage_clients delete <client_id>`

### 6. Google Cloud Storage Setup

1. Create a Google Cloud Storage bucket (if you haven't already)
2. Create a Service Account with Storage Admin role
3. Download the service account JSON key file
4. Update `GOOGLE_APPLICATION_CREDENTIALS` in `.env` with the path to your key file (e.g. `path/to/your/service-account-key.json`)

**Security:** Do not commit `.env` or any credentials file (e.g. `credentials.json`) to the repository. Keep keys outside the repo or in a secure location. If a key was ever exposed, rotate it in the Google Cloud Console.

## Running the Application

### Development Mode

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:

- **Interactive API Docs (Swagger UI)**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

## API Endpoints

### Health Check

```bash
GET /health
```

Returns the health status of the API. This endpoint does not require authentication.

### Upload Document

```bash
POST /documently/api/v1/upload
```

**Authentication Required:**
- `X-Client-Id`: Client ID header (required)
- `X-Client-Secret`: Client secret header (required)

**Request:**
- `file`: The document file (multipart/form-data)
- `user_id`: User ID for organizing documents (form field)

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded successfully",
  "url": "https://storage.googleapis.com/bucket-name/documents.in/user123/document.pdf",
  "user_id": "user123",
  "filename": "document.pdf"
}
```

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/documently/api/v1/upload" \
  -H "X-Client-Id: your_client_id" \
  -H "X-Client-Secret: your_client_secret" \
  -F "file=@/path/to/your/document.pdf" \
  -F "user_id=user123"
```

**Example using Python requests:**
```python
import requests

url = "http://localhost:8000/documently/api/v1/upload"
headers = {
    "X-Client-Id": "your_client_id",
    "X-Client-Secret": "your_client_secret"
}
files = {"file": open("document.pdf", "rb")}
data = {"user_id": "user123"}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

## Project Structure

```
dcumently/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── models.py            # Database models
│   ├── auth.py              # Authentication dependencies
│   ├── api_routes.py        # API routes with authentication
│   ├── utils.py             # Utility functions
│   ├── services/
│   │   ├── __init__.py
│   │   └── storage_service.py  # Google Cloud Storage service
│   └── scripts/
│       ├── __init__.py
│       ├── init_db.py       # Database initialization script
│       └── manage_clients.py # Client credential management
├── requirements.txt
├── .env.example
├── .env                     # Your local configuration (not in git)
├── .gitignore
└── README.md
```

## Authentication

All API endpoints under `/documently/api/v1/` require authentication using client credentials:

1. **Client ID and Secret**: Stored in PostgreSQL database (secrets are hashed using bcrypt)
2. **Headers Required**: 
   - `X-Client-Id`: Your client ID
   - `X-Client-Secret`: Your client secret (plain text, will be verified against hashed version)

3. **Managing Clients**: Use the management script to create, list, activate, deactivate, or delete client credentials.

## Error Handling

The API includes comprehensive error handling:

- **401 Unauthorized**: Invalid or missing client credentials
- **400 Bad Request**: Invalid input (empty user_id, filename, or file content)
- **500 Internal Server Error**: Google Cloud Storage errors or unexpected errors

All errors are logged with appropriate detail levels.

## Security Notes

- Never commit your `.env` file or service account keys to version control
- Client secrets are hashed using bcrypt before storage
- The service account key should have minimal required permissions (Storage Admin for the specific bucket)
- Keep your client credentials secure and rotate them regularly
- The returned URLs are publicly accessible - ensure this meets your security requirements
- Use HTTPS in production environments

## License

This project is provided as-is for use in your applications.

