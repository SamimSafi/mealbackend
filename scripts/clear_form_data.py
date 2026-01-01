"""Script to clear form data from database for re-syncing from Kobo."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Form, Submission, RawSubmission, Indicator, SyncLog

def clear_form_data(form_id: int = None, clear_all: bool = False):
    """
    Clear form data from database.
    
    Args:
        form_id: Specific form ID to clear (None = all forms)
        clear_all: If True, clear all forms AND delete all form records
    """
    db: Session = SessionLocal()
    
    try:
        if clear_all:
            # Clear all forms
            print("Clearing data for ALL forms...")
            
            # Delete indicators
            indicators_count = db.query(Indicator).count()
            db.query(Indicator).delete()
            print(f"  Deleted {indicators_count} indicators")
            
            # Delete submissions
            submissions_count = db.query(Submission).count()
            db.query(Submission).delete()
            print(f"  Deleted {submissions_count} submissions")
            
            # Delete raw submissions
            raw_submissions_count = db.query(RawSubmission).count()
            db.query(RawSubmission).delete()
            print(f"  Deleted {raw_submissions_count} raw submissions")
            
            # Optionally clear sync logs
            sync_logs_count = db.query(SyncLog).count()
            db.query(SyncLog).delete()
            print(f"  Deleted {sync_logs_count} sync logs")
            
            # Delete all forms (cascade will handle related data)
            forms_count = db.query(Form).count()
            db.query(Form).delete()
            print(f"  Deleted {forms_count} forms")
            
        elif form_id:
            # Clear specific form
            form = db.query(Form).filter(Form.id == form_id).first()
            if not form:
                print(f"Form {form_id} not found!")
                return
            
            print(f"Clearing data for form {form_id} ({form.title})...")
            
            # Delete indicators
            indicators_count = db.query(Indicator).filter(Indicator.form_id == form_id).count()
            db.query(Indicator).filter(Indicator.form_id == form_id).delete()
            print(f"  Deleted {indicators_count} indicators")
            
            # Delete submissions
            submissions_count = db.query(Submission).filter(Submission.form_id == form_id).count()
            db.query(Submission).filter(Submission.form_id == form_id).delete()
            print(f"  Deleted {submissions_count} submissions")
            
            # Delete raw submissions
            raw_submissions_count = db.query(RawSubmission).filter(RawSubmission.form_id == form_id).count()
            db.query(RawSubmission).filter(RawSubmission.form_id == form_id).delete()
            print(f"  Deleted {raw_submissions_count} raw submissions")
            
            # Delete sync logs for this form
            sync_logs_count = db.query(SyncLog).filter(SyncLog.form_id == form_id).count()
            db.query(SyncLog).filter(SyncLog.form_id == form_id).delete()
            print(f"  Deleted {sync_logs_count} sync logs")
            
            # Reset last_synced_at
            form.last_synced_at = None
            print(f"  Reset last_synced_at")
        else:
            print("Error: Please specify either form_id or use --all flag")
            print("Usage: python clear_form_data.py [form_id] [--all]")
            return
        
        db.commit()
        print("\n[SUCCESS] Data cleared successfully!")
        print("You can now re-sync from Kobo using the sync endpoint.")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Error clearing data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all" or sys.argv[1] == "-a":
            clear_form_data(clear_all=True)
        else:
            try:
                form_id = int(sys.argv[1])
                clear_form_data(form_id=form_id)
            except ValueError:
                print("Error: form_id must be a number")
                print("Usage: python clear_form_data.py [form_id] [--all]")
    else:
        print("Usage: python clear_form_data.py [form_id] [--all]")
        print("\nExamples:")
        print("  python clear_form_data.py 1        # Clear data for form ID 1")
        print("  python clear_form_data.py --all    # Clear data AND delete all forms")

