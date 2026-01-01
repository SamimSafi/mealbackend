"""ETL pipeline for processing Kobo data."""
import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from kobo_client import KoboClient
from models import Form, Indicator, Submission, SyncLog, RawSubmission

logger = logging.getLogger(__name__)


class ETLPipeline:
    """ETL pipeline for processing Kobo form data."""

    def __init__(self, db: Session, kobo_client: Optional[KoboClient] = None):
        """Initialize ETL pipeline."""
        self.db = db
        self.kobo_client = kobo_client or KoboClient()

    def clean_submission_data(self, submission: dict[str, Any]) -> dict[str, Any]:
        """
        Clean and normalize submission data.

        Responsibilities:
        - Flatten nested JSON structures
        - Coerce numeric fields to numbers
        - Normalize date/time strings
        - Normalize simple text fields (strip whitespace)
        - Derive helper fields (e.g. age_group)
        - Attach validation flags (is_valid, validation_errors)
        """
        # First flatten the raw JSON to a simple key/value mapping
        flattened: dict[str, Any] = {}
        for key, value in submission.items():
            # Handle nested structures
            if isinstance(value, dict):
                flattened.update(self._flatten_dict(value, prefix=key))
            elif isinstance(value, list):
                # Handle lists (e.g., repeat groups)
                flattened[f"{key}_count"] = len(value)
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        flattened.update(self._flatten_dict(item, prefix=f"{key}_{i}"))
            else:
                flattened[key] = value

        cleaned: dict[str, Any] = {}
        validation_errors: list[str] = []
        is_valid = True

        for key, value in flattened.items():
            # Normalize text fields
            if isinstance(value, str):
                value = value.strip()

            # Basic type-aware cleaning heuristics
            lowered_key = key.lower()

            # Numeric fields (ids, ages, counts, numeric measurements)
            if any(tok in lowered_key for tok in ["age", "count", "number", "num", "qty", "quantity"]):
                try:
                    if value not in (None, ""):
                        value = float(value)
                except (ValueError, TypeError):
                    validation_errors.append(f"Invalid numeric value for {key}: {value!r}")
                    is_valid = False

            # Date / time-like fields
            if any(tok in lowered_key for tok in ["date", "time"]):
                # Kobo often sends ISO timestamps already – keep them as-is if they parse,
                # otherwise fall back to the original string.
                from datetime import datetime

                if isinstance(value, str) and value:
                    parsed = None
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]:
                        try:
                            parsed = datetime.strptime(value.split("T")[0], fmt)
                            break
                        except Exception:
                            continue
                    if parsed:
                        value = parsed.isoformat()
                    else:
                        # Keep original but mark validation soft error
                        validation_errors.append(f"Unrecognized date format for {key}: {value!r}")

            cleaned[key] = value

        # Derive age_group from common age fields if present
        age_value = None
        for candidate in ["age", "age_of_respondent", "respondent_age"]:
            if candidate in cleaned and cleaned[candidate] not in (None, ""):
                age_value = cleaned[candidate]
                break

        if age_value is not None:
            try:
                age_float = float(age_value)
                cleaned["age_group"] = self._get_age_group(age_float)
            except (ValueError, TypeError):
                # If age cannot be parsed, keep record but flag as partially invalid
                validation_errors.append(f"Invalid age value: {age_value!r}")
                is_valid = False

        # Attach validation metadata into the cleaned payload
        cleaned["is_valid"] = is_valid
        if validation_errors:
            cleaned["validation_errors"] = validation_errors

        return cleaned

    def _flatten_dict(self, d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten nested dictionary."""
        flattened = {}
        for key, value in d.items():
            new_key = f"{prefix}_{key}" if prefix else key
            if isinstance(value, dict):
                flattened.update(self._flatten_dict(value, prefix=new_key))
            elif isinstance(value, list):
                flattened[f"{new_key}_count"] = len(value)
            else:
                flattened[new_key] = value
        return flattened

    @staticmethod
    def _get_age_group(age: float) -> str:
        """Convert numeric age into an age group bucket."""
        if age < 5:
            return "0-4"
        if age < 12:
            return "5-11"
        if age < 18:
            return "12-17"
        if age < 30:
            return "18-29"
        if age < 45:
            return "30-44"
        if age < 60:
            return "45-59"
        return "60+"

    def extract_location(self, submission_data: dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
        """Extract location data from submission."""
        lat = None
        lng = None
        location_name = None

        # Common location field names in Kobo
        location_fields = ["_geolocation", "geolocation", "location", "coordinates"]
        for field in location_fields:
            if field in submission_data:
                loc = submission_data[field]
                if isinstance(loc, list) and len(loc) >= 2:
                    lat, lng = float(loc[0]), float(loc[1])
                elif isinstance(loc, dict):
                    lat = loc.get("latitude") or loc.get("lat")
                    lng = loc.get("longitude") or loc.get("lng") or loc.get("lon")
                    location_name = loc.get("name") or loc.get("address")

        # Check for separate lat/lng fields
        if lat is None:
            for key in submission_data.keys():
                if "lat" in key.lower() and submission_data[key]:
                    try:
                        lat = float(submission_data[key])
                    except (ValueError, TypeError):
                        pass
        if lng is None:
            for key in submission_data.keys():
                if "lng" in key.lower() or "lon" in key.lower():
                    if submission_data[key]:
                        try:
                            lng = float(submission_data[key])
                        except (ValueError, TypeError):
                            pass

        return lat, lng, location_name

    def sync_form(self, kobo_form_id: str, sync_type: str = "incremental") -> SyncLog:
        """Sync a form from Kobo."""
        sync_log = SyncLog(
            sync_type=sync_type,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(sync_log)
        self.db.flush()

        try:
            # Get or create form
            form = self.db.query(Form).filter(Form.kobo_form_id == kobo_form_id).first()
            kobo_form = self.kobo_client.get_form(kobo_form_id)

            if not kobo_form:
                raise ValueError(f"Form {kobo_form_id} not found in Kobo")

            if not form:
                # KoboToolbox API v2 uses 'name' for title
                form = Form(
                    kobo_form_id=kobo_form_id,
                    title=kobo_form.get("name") or kobo_form.get("title") or kobo_form_id,
                    description=kobo_form.get("settings", {}).get("description", "") or kobo_form.get("description", ""),
                    form_schema=kobo_form,
                )
                self.db.add(form)
                self.db.flush()
            else:
                form.title = kobo_form.get("name") or kobo_form.get("title") or form.title
                form.description = kobo_form.get("settings", {}).get("description", "") or kobo_form.get("description", form.description)
                form.form_schema = kobo_form
                form.last_synced_at = datetime.utcnow()

            sync_log.form_id = form.id

            # Get submissions
            if sync_type == "full":
                submissions = self.kobo_client.get_all_form_submissions(kobo_form_id)
            else:
                # Incremental: only get new submissions
                submissions = self.kobo_client.get_form_submissions(kobo_form_id, limit=1000)

            records_added = 0
            records_updated = 0

            for kobo_submission in submissions:
                submission_id = kobo_submission.get("_id") or kobo_submission.get("id")

                if not submission_id:
                    continue

                submission_id_str = str(submission_id)
                
                # Store raw submission
                raw_submission = (
                    self.db.query(RawSubmission)
                    .filter(RawSubmission.kobo_submission_id == submission_id_str)
                    .first()
                )
                
                if not raw_submission:
                    raw_submission = RawSubmission(
                        form_id=form.id,
                        kobo_submission_id=submission_id_str,
                        submission_json=kobo_submission,
                    )
                    self.db.add(raw_submission)
                else:
                    raw_submission.submission_json = kobo_submission

                # Check if cleaned submission exists
                existing = (
                    self.db.query(Submission)
                    .filter(Submission.kobo_submission_id == submission_id_str)
                    .first()
                )

                # Clean and normalize data
                cleaned_data = self.clean_submission_data(kobo_submission)
                lat, lng, loc_name = self.extract_location(kobo_submission)
                
                submitted_at = None
                if "_submission_time" in kobo_submission:
                    try:
                        submitted_at = datetime.fromisoformat(
                            kobo_submission["_submission_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                if existing:
                    # Update existing
                    existing.submission_data = kobo_submission
                    existing.cleaned_data = cleaned_data
                    existing.location_lat = lat
                    existing.location_lng = lng
                    existing.location_name = loc_name
                    existing.updated_at = datetime.utcnow()
                    records_updated += 1
                else:
                    # Create new
                    submission = Submission(
                        form_id=form.id,
                        kobo_submission_id=submission_id_str,
                        submission_data=kobo_submission,
                        cleaned_data=cleaned_data,
                        submitted_at=submitted_at,
                        location_lat=lat,
                        location_lng=lng,
                        location_name=loc_name,
                    )
                    self.db.add(submission)
                    records_added += 1

            sync_log.records_processed = len(submissions)
            sync_log.records_added = records_added
            sync_log.records_updated = records_updated
            sync_log.status = "success"
            sync_log.completed_at = datetime.utcnow()

            self.db.commit()

            # Compute indicators after syncing
            self.compute_indicators(form.id)
            
            # Emit WebSocket event for real-time updates
            try:
                from websocket_manager import manager
                import asyncio
                
                # Create async task to broadcast update
                message = {
                    "type": "form_updated",
                    "form_id": form.id,
                    "records_added": records_added,
                    "records_updated": records_updated,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                # Run in event loop if available
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(manager.broadcast_to_form(form.id, message))
                    else:
                        loop.run_until_complete(manager.broadcast_to_form(form.id, message))
                except RuntimeError:
                    # No event loop, create new one
                    asyncio.run(manager.broadcast_to_form(form.id, message))
            except Exception as e:
                logger.warning(f"Failed to emit WebSocket event: {e}")

            return sync_log

        except Exception as e:
            logger.error(f"Error syncing form {kobo_form_id}: {e}", exc_info=True)
            sync_log.status = "error"
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            raise

    def compute_indicators(self, form_id: int) -> list[Indicator]:
        """Compute indicators for a form."""
        form = self.db.query(Form).filter(Form.id == form_id).first()
        if not form:
            return []

        # Get all submissions for the form
        submissions = self.db.query(Submission).filter(Submission.form_id == form_id).all()

        if not submissions:
            return []

        # Convert to DataFrame for easier computation
        submission_data = [s.submission_data for s in submissions]
        df = pd.DataFrame([self.clean_submission_data(s) for s in submission_data])

        indicators = []

        # Auto-detect and compute common indicators
        # 1. Total count
        count_indicator = self._get_or_create_indicator(
            form_id, "Total Submissions", "count", {"field": "_all"}
        )
        count_indicator.value = len(submissions)
        indicators.append(count_indicator)

        # 2. Count by category (if category field exists)
        category_fields = [col for col in df.columns if "category" in col.lower() or "type" in col.lower()]
        for field in category_fields[:3]:  # Limit to first 3 category fields
            if df[field].notna().any():
                counts = df[field].value_counts().to_dict()
                for category, count in counts.items():
                    indicator_name = f"Count: {field} = {category}"
                    indicator = self._get_or_create_indicator(
                        form_id, indicator_name, "count", {"field": field, "value": category}
                    )
                    indicator.value = float(count)
                    indicators.append(indicator)

        # 3. Percentage indicators
        yes_no_fields = [col for col in df.columns if any(x in col.lower() for x in ["yes", "no", "y/n"])]
        for field in yes_no_fields[:5]:  # Limit to first 5 yes/no fields
            if df[field].notna().any():
                yes_count = (df[field].astype(str).str.lower() == "yes").sum()
                total = df[field].notna().sum()
                if total > 0:
                    percentage = (yes_count / total) * 100
                    indicator_name = f"Percentage: {field} = Yes"
                    indicator = self._get_or_create_indicator(
                        form_id, indicator_name, "percentage", {"field": field, "value": "yes"}
                    )
                    indicator.value = percentage
                    indicators.append(indicator)

        # 4. Average indicators (for numeric fields)
        numeric_fields = df.select_dtypes(include=["number"]).columns
        for field in numeric_fields[:5]:  # Limit to first 5 numeric fields
            if df[field].notna().any():
                avg = df[field].mean()
                indicator_name = f"Average: {field}"
                indicator = self._get_or_create_indicator(
                    form_id, indicator_name, "average", {"field": field}
                )
                indicator.value = float(avg)
                indicators.append(indicator)

        self.db.commit()
        return indicators

    def _get_or_create_indicator(
        self, form_id: int, name: str, indicator_type: str, computation_rule: dict[str, Any]
    ) -> Indicator:
        """Get or create an indicator."""
        indicator = (
            self.db.query(Indicator)
            .filter(Indicator.form_id == form_id, Indicator.name == name)
            .first()
        )
        if not indicator:
            indicator = Indicator(
                form_id=form_id,
                name=name,
                indicator_type=indicator_type,
                computation_rule=computation_rule,
            )
            self.db.add(indicator)
        indicator.computed_at = datetime.utcnow()
        return indicator

    def sync_all_forms(self, sync_type: str = "incremental") -> list[SyncLog]:
        """Sync all forms from Kobo."""
        forms = self.kobo_client.get_forms()
        sync_logs = []

        for kobo_form in forms:
            # KoboToolbox API v2 uses 'uid' for form identifier
            form_id = kobo_form.get("uid") or kobo_form.get("formid") or kobo_form.get("id")
            if form_id:
                try:
                    sync_log = self.sync_form(str(form_id), sync_type=sync_type)
                    sync_logs.append(sync_log)
                except Exception as e:
                    logger.error(f"Failed to sync form {form_id}: {e}")

        return sync_logs

