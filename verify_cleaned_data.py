#!/usr/bin/env python
"""Verify that cleaned_data has decoded values."""

from database import SessionLocal
from models import Submission
import json

db = SessionLocal()

sub = db.query(Submission).filter(Submission.form_id == 16).first()

if sub:
    print("Submission Data (raw codes):")
    if sub.submission_data:
        for key in ['info/province', 'info/district', 'beneficiary/respondent_gender']:
            val = sub.submission_data.get(key)
            print(f"  {key}: {val}")
    
    print("\nCleaned Data (decoded labels):")
    if sub.cleaned_data:
        for key in ['info/province', 'info/district', 'beneficiary/respondent_gender']:
            val = sub.cleaned_data.get(key)
            print(f"  {key}: {val}")

db.close()
