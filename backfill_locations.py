"""Script to backfill province/district from form data and location_name from GPS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
from database import SessionLocal
from models import Submission, Form
from etl import ETLPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_locations(limit: int = None, force: bool = False):
    """
    Backfill location data for existing submissions.
    
    - province/district: from form data (user input)
    - location_name: from GPS reverse geocoding
    
    Args:
        limit: Maximum number of records to process (None for all)
        force: If True, re-process even if location_name exists
    """
    db = SessionLocal()
    etl = ETLPipeline(db)
    
    try:
        # Find submissions that need backfilling
        query = db.query(Submission)
        
        if not force:
            # Only process submissions with GPS coordinates but missing location_name
            query = query.filter(
                Submission.location_lat.isnot(None),
                Submission.location_lng.isnot(None),
                (Submission.location_name.is_(None) | (Submission.location_name == ""))
            )
        else:
            # Process all submissions with GPS coordinates
            query = query.filter(
                Submission.location_lat.isnot(None),
                Submission.location_lng.isnot(None)
            )
        
        if limit:
            query = query.limit(limit)
        
        submissions = query.all()
        
        logger.info(f"Found {len(submissions)} submissions to backfill")
        
        if not submissions:
            logger.info("No submissions need backfilling")
            return
        
        updated_count = 0
        for i, submission in enumerate(submissions):
            logger.info(f"[{i+1}/{len(submissions)}] Processing submission {submission.kobo_submission_id}...")
            
            cleaned_data = dict(submission.cleaned_data) if submission.cleaned_data else {}
            submission_data = submission.submission_data or {}
            
            # 1. Extract province/district from FORM DATA (if not already set)
            if not submission.province or not submission.district:
                form_province, form_district = etl.extract_province_district_from_data(
                    submission_data, cleaned_data
                )
                
                if form_province and not submission.province:
                    submission.province = form_province
                    cleaned_data["province"] = form_province
                    logger.info(f"  -> Province from form: {form_province}")
                
                if form_district and not submission.district:
                    submission.district = form_district
                    cleaned_data["district"] = form_district
                    logger.info(f"  -> District from form: {form_district}")
            
            # 2. Reverse geocode GPS coordinates for location_name
            gps_province, gps_detailed_location = etl.reverse_geocode(
                submission.location_lat, submission.location_lng
            )
            
            if gps_detailed_location or gps_province:
                # Use detailed GPS location directly
                if gps_detailed_location:
                    submission.location_name = gps_detailed_location
                elif gps_province:
                    submission.location_name = gps_province
                
                # Store GPS-resolved values in cleaned_data for reference
                if gps_province:
                    cleaned_data["gps_resolved_province"] = gps_province
                if gps_detailed_location:
                    cleaned_data["gps_resolved_location"] = gps_detailed_location
                
                logger.info(f"  -> Location name (GPS): {submission.location_name}")
                updated_count += 1
            else:
                logger.warning(f"  -> No GPS data for: {submission.location_lat}, {submission.location_lng}")
                
                # Fallback: use form data for location_name if no GPS resolved
                if not submission.location_name:
                    if submission.province and submission.district:
                        submission.location_name = f"{submission.district}, {submission.province}"
                    elif submission.province:
                        submission.location_name = submission.province
                    elif submission.district:
                        submission.location_name = submission.district
            
            submission.cleaned_data = cleaned_data
            
            # Commit every 10 records
            if (i + 1) % 10 == 0:
                db.commit()
                logger.info(f"Committed {i + 1} records")
        
        db.commit()
        logger.info(f"Successfully backfilled {updated_count} submissions")
        
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill location data for submissions")
    parser.add_argument("--limit", type=int, help="Limit number of records to process")
    parser.add_argument("--force", action="store_true", help="Re-process all GPS coordinates")
    
    args = parser.parse_args()
    backfill_locations(limit=args.limit, force=args.force)
