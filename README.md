# Kobo Dashboard Backend

A FastAPI-based backend for managing and visualizing data from KoboToolbox forms.

## Features

- **ETL Pipeline**: Automated data fetching, cleaning, and transformation from KoboToolbox API
- **Dynamic Indicators**: Auto-computation of indicators based on form fields
- **JWT Authentication**: Secure token-based authentication
- **User Management**: Role-based access control (admin, viewer, editor)
- **RESTful API**: Comprehensive API endpoints for forms, submissions, indicators, and dashboards
- **Webhook Support**: Real-time sync via webhooks from KoboToolbox
- **SQLite Database**: Lightweight, file-based database for easy deployment

## Prerequisites

- Python 3.9+
- pip or poetry

## Installation

1. **Clone the repository** (if applicable) or navigate to the backend directory:
   ```bash
   cd mealbackend
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

   Required environment variables:
   - `KOBO_API_TOKEN`: Your KoboToolbox API token
   - `KOBO_USERNAME`: Your KoboToolbox username
   - `SECRET_KEY`: A secret key for JWT tokens (generate with `openssl rand -hex 32`)

5. **Initialize the database**:
   ```bash
   python scripts/init_db.py
   ```

## Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI) is available at `http://localhost:8000/docs`

## Default Credentials

After initialization, a default admin user is created:
- **Username**: `admin`
- **Password**: `admin123`

**⚠️ IMPORTANT**: Change the default password in production!

## Creating Users

You can create users via the API or using the script:

```bash
python scripts/create_user.py <username> <email> <password> [role] [full_name]
```

Example:
```bash
python scripts/create_user.py john john@example.com password123 viewer "John Doe"
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get JWT token
- `POST /api/auth/register` - Register a new user
- `GET /api/auth/me` - Get current user info

### Forms
- `GET /api/forms` - List all forms
- `GET /api/forms/{form_id}` - Get form details

### Submissions
- `GET /api/submissions` - List submissions (optional `form_id` query param)
- `GET /api/submissions/{submission_id}` - Get submission details

### Indicators
- `GET /api/indicators` - List indicators (optional `form_id` and `category` query params)
- `GET /api/indicators/{indicator_id}` - Get indicator details

### Dashboard
- `GET /api/dashboard/summary` - Get dashboard summary
- `GET /api/dashboard/indicators` - Get indicator dashboard data
- `GET /api/dashboard/accountability` - Get accountability/complaints dashboard data

### Sync (Admin only)
- `POST /api/sync` - Sync forms from Kobo
- `GET /api/sync/logs` - Get sync logs

### User Management (Admin only)
- `GET /api/users` - List users
- `GET /api/users/{user_id}` - Get user details
- `PUT /api/users/{user_id}` - Update user
- `POST /api/users/{user_id}/permissions` - Add user permission

### Webhooks
- `POST /api/webhooks/kobo` - Webhook endpoint for Kobo form submissions

## Testing

Run tests with pytest:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=. --cov-report=html
```

## Database Schema

The application uses SQLite with the following main tables:

- **users**: User accounts and authentication
- **user_permissions**: Granular permissions for users
- **forms**: Kobo form metadata
- **submissions**: Form submission data
- **indicators**: Computed indicators
- **sync_logs**: ETL operation logs

## ETL Pipeline

The ETL pipeline (`etl.py`) handles:

1. **Extract**: Fetch forms and submissions from KoboToolbox API
2. **Transform**: Clean data, handle missing values, normalize structures
3. **Load**: Store processed data in SQLite
4. **Compute Indicators**: Automatically calculate indicators based on form fields

### Indicator Types

The system automatically detects and computes:
- **Count**: Total submissions, counts by category
- **Percentage**: Yes/No percentages, category distributions
- **Average**: Numeric field averages
- **Sum**: Aggregated numeric values

## Webhook Configuration

To enable real-time sync, configure webhooks in KoboToolbox:

1. Go to your form settings in KoboToolbox
2. Navigate to Webhooks
3. Add webhook URL: `https://your-domain.com/api/webhooks/kobo`
4. Select events: `submission.created`, `submission.updated`

## Architecture

```
mealbackend/
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── database.py          # Database setup
├── models.py            # SQLAlchemy models
├── schemas.py           # Pydantic schemas
├── auth.py              # Authentication utilities
├── kobo_client.py       # KoboToolbox API client
├── etl.py               # ETL pipeline
├── tests/               # Test suite
└── scripts/             # Utility scripts
```

## Deployment

### Production Considerations

1. **Change default credentials**: Update admin password
2. **Use strong SECRET_KEY**: Generate with `openssl rand -hex 32`
3. **Configure CORS**: Update `CORS_ORIGINS` in `.env`
4. **Database backup**: Regularly backup SQLite database
5. **HTTPS**: Use reverse proxy (nginx) with SSL
6. **Environment variables**: Never commit `.env` file

### Using with Gunicorn

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Troubleshooting

### Database locked errors
- Ensure only one process accesses the database
- Check for long-running transactions

### Kobo API errors
- Verify `KOBO_API_TOKEN` is correct
- Check API rate limits
- Ensure form IDs are correct

### Authentication issues
- Verify JWT token expiration settings
- Check `SECRET_KEY` is set correctly
- Ensure token is sent in `Authorization: Bearer <token>` header

## License

[Your License Here]

