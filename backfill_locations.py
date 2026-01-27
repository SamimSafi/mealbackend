"""Script to backfill province/district from form data and location_name from GPS.
Reads location_lat/location_lng from the database (saved at sync from start-geopoint)
and reverse geocodes them; no Kobo or sync needed. Run after sync."""
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
            
            # 2. Reverse geocode GPS (Nominatim can be wrong, e.g. Sholgara vs Khoshal Khan Kabul)
            gps_province, gps_detailed_location = etl.reverse_geocode(
                submission.location_lat, submission.location_lng
            )
            if gps_province:
                cleaned_data["gps_resolved_province"] = gps_province
            if gps_detailed_location:
                cleaned_data["gps_resolved_location"] = gps_detailed_location

            # Survey accuracy: compare form province vs GPS (from start-geopoint or manual gps_location) to detect wrong surveys
            gps_consistent, survey_warning = etl._compute_gps_consistent(submission.province, gps_province)
            cleaned_data["gps_consistent"] = gps_consistent
            if survey_warning:
                cleaned_data["survey_location_warning"] = survey_warning

            # Prefer form-based location over GPS for display; use GPS only when form has nothing
            form_place = etl.extract_form_place_name(submission_data, cleaned_data)
            form_loc = ", ".join(p for p in (submission.district, submission.province) if p) if (submission.district or submission.province) else None
            if form_place:
                submission.location_name = form_place
                logger.info(f"  -> Location name (form place): {submission.location_name}")
                updated_count += 1
            elif form_loc:
                submission.location_name = form_loc
                logger.info(f"  -> Location name (form province/district): {submission.location_name}")
                updated_count += 1
            elif gps_detailed_location or gps_province:
                submission.location_name = gps_detailed_location or gps_province
                logger.info(f"  -> Location name (GPS): {submission.location_name}")
                updated_count += 1
            else:
                logger.warning(f"  -> No location for: {submission.location_lat}, {submission.location_lng}")

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
