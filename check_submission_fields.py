#!/usr/bin/env python
"""Check what fields are in submissions."""

from database import SessionLocal
from models import Submission

db = SessionLocal()

submissions = db.query(Submission).filter(Submission.form_id == 16).limit(1).all()

if submissions:
    sub = submissions[0]
    payload = sub.cleaned_data or sub.submission_data or {}
    
    print("Fields in first submission:")
    for key in sorted(payload.keys()):
        if 'province' in key.lower() or 'gender' in key.lower() or 'location' in key.lower():
            print(f"  {key}: {payload[key]}")

db.close()
