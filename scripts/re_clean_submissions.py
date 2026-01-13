#!/usr/bin/env python
"""Re-clean all existing submissions with choice decoding."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Form as FormModel, Submission
from etl import ETLPipeline

def re_clean_all_submissions():
    """Re-clean all submissions to decode choice codes."""
    db = SessionLocal()
    
    try:
        forms = db.query(FormModel).all()
        total_submissions = 0
        
        for form in forms:
            etl = ETLPipeline(db)
            submissions = db.query(Submission).filter(Submission.form_id == form.id).all()
            
            if not submissions:
                continue
            
            print(f"\nProcessing form {form.id}: {form.title}")
            print(f"  Found {len(submissions)} submissions")
            
            for i, sub in enumerate(submissions):
                if sub.submission_data and isinstance(sub.submission_data, dict):
                    cleaned = etl.clean_submission_data(sub.submission_data, form=form)
                    sub.cleaned_data = cleaned
                    
                    if (i + 1) % 10 == 0:
                        print(f"  Cleaned {i + 1}/{len(submissions)}")
            
            db.commit()
            total_submissions += len(submissions)
            print(f"  Committed {len(submissions)} submissions")
        
        print(f"\n[OK] Re-cleaned {total_submissions} total submissions")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    re_clean_all_submissions()
