import sys
from pathlib import Path
sys.path.insert(0, '.')
from config import settings
print(f'DATABASE_URL: {settings.DATABASE_URL}')
db_path = settings.DATABASE_URL.replace("sqlite:///", "")
abs_path = Path(db_path).resolve()
print(f'Absolute path: {abs_path}')
print(f'Parent dir: {abs_path.parent}')
print(f'Exists: {abs_path.exists()}')
print(f'Parent exists: {abs_path.parent.exists()}')
