# PythonAnywhere Deployment Guide

## Database Setup

### Architecture
- **Local Development**: SQLite (file-based, no setup needed)
- **Production (PythonAnywhere)**: MySQL (hosted on PythonAnywhere servers)

## Setup for Local Development

1. **Default Configuration**
   - SQLite database is automatically created in project root
   - File: `kobo_dashboard.db`
   - No additional setup needed!

2. **.env Configuration (Optional)**
   ```
   ENVIRONMENT=local
   SQLITE_PATH=kobo_dashboard.db
   ```

## Setup for PythonAnywhere

### 1. MySQL Database Configuration

PythonAnywhere MySQL Details:
- **Host**: samimsafi.mysql.pythonanywhere-services.com
- **Username**: samimsafi
- **Password**: Meal@123
- **Database**: samimsafi$kobo_dashboard

### 2. Set Environment Variables in PythonAnywhere

Go to **Account** → **Web app** → Your app → **Environment variables**

Add these variables:

```
ENVIRONMENT=production
MYSQL_HOST=samimsafi.mysql.pythonanywhere-services.com
MYSQL_USER=samimsafi
MYSQL_PASSWORD=Meal@123
MYSQL_DATABASE=samimsafi$kobo_dashboard
```

### 3. Install MySQL Driver

In PythonAnywhere bash console:
```bash
pip install pymysql
```

### 4. Update Web App Configuration

1. Go to **Web** → Your app
2. Update **WSGI configuration file** to ensure it loads `.env` variables
3. Reload the web app

### 5. Verify Database Connection

- The database will auto-initialize on first app request
- Tables and default admin user will be created automatically
- Login: admin / admin123

## Database Auto-Migration

The system automatically:
- **Creates tables** if missing
- **Detects schema changes** and updates the database
- **Creates default admin** user (username: `admin`, password: `admin123`)
- **Tracks migrations** with unique GUIDs in `database_migrations` table
- **Works on both SQLite and MySQL** without code changes

No manual migrations needed! Just update models and restart the app.

## Environment Variables Summary

| Variable | Local | Production |
|----------|-------|-----------|
| ENVIRONMENT | local | production |
| SQLITE_PATH | kobo_dashboard.db | (not used) |
| MYSQL_HOST | (not used) | samimsafi.mysql.pythonanywhere-services.com |
| MYSQL_USER | (not used) | samimsafi |
| MYSQL_PASSWORD | (not used) | Meal@123 |
| MYSQL_DATABASE | (not used) | samimsafi$kobo_dashboard |

## Troubleshooting

### 500 Error: "ModuleNotFoundError: No module named 'pymysql'"
```bash
pip install pymysql
```

### 500 Error: "Access denied for user 'samimsafi'"
- Check MySQL credentials in environment variables
- Verify database name: `samimsafi$kobo_dashboard`

### Connection Refused to MySQL
- Verify MYSQL_HOST is correct: `samimsafi.mysql.pythonanywhere-services.com`
- Check MySQL database is enabled in PythonAnywhere account

### Database Not Updating After Code Changes
- Force app reload: Web → Reload [yoursite.pythonanywhere.com]
- Clear Python cache: Bash → `find . -type d -name __pycache__ -exec rm -r {} +` 

### Tables Not Created
- Check app logs: Web → Error log
- Ensure ENVIRONMENT=production in variables
- Manually trigger migration by reloading web app
