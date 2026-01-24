"""Standard filter parsing and application for reports."""
import logging
from datetime import datetime, date
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session, Query
from sqlalchemy import and_, or_, func

from models import Submission

logger = logging.getLogger(__name__)


def get_nested_field_value(obj: Dict[str, Any], field_path: str) -> Any:
    """
    Retrieve a value from a nested dictionary using dot notation or slash notation.
    
    Examples:
        get_nested_field_value({"info": {"province": "Kabul"}}, "info/province") -> "Kabul"
        get_nested_field_value({"info": {"province": "Kabul"}}, "info.province") -> "Kabul"
    """
    if not obj or not isinstance(obj, dict):
        return None
    
    parts = field_path.replace(".", "/").split("/")
    
    value = obj
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        
        if value is None:
            return None
    
    return value


def set_nested_field_value(obj: Dict[str, Any], field_path: str, value: Any) -> None:
    """Set a value in a nested dictionary using slash notation."""
    if not obj or not isinstance(obj, dict):
        return
    
    parts = field_path.split("/")
    
    current = obj
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value


@dataclass
class LocationFilter:
    """Geographic dimension filter."""
    dimension_1: Optional[str] = None
    dimension_2: Optional[str] = None
    dimension_3: Optional[str] = None
    
    def is_empty(self) -> bool:
        """Check if all dimensions are empty."""
        return all(v is None for v in [self.dimension_1, self.dimension_2, self.dimension_3])
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dictionary."""
        return {
            "dimension_1": self.dimension_1,
            "dimension_2": self.dimension_2,
            "dimension_3": self.dimension_3
        }


class FilterContext:
    """
    Encapsulates all filtering logic for reports.
    Applies filters uniformly across all report types.
    """
    
    def __init__(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        locations: Optional[List[LocationFilter]] = None,
        form_ids: Optional[List[int]] = None,
        field_filters: Optional[Dict[str, Any]] = None,
        exclude_incomplete: bool = False,
        geo_fields: Optional[Dict[str, str]] = None,  # Maps dimension_1/2/3 to field names
    ):
        """
        Initialize filter context.
        
        Args:
            date_from: Start date for filtering
            date_to: End date for filtering
            locations: Geographic filters (supports multi-level hierarchy)
            form_ids: Filter by form IDs
            field_filters: Direct field equality filters (field_name -> value or list of values)
            exclude_incomplete: Exclude submissions with validation errors
            geo_fields: Map dimension names to field names in data
                       E.g., {"dimension_1": "info/province", "dimension_2": "info/district"}
        """
        self.date_from = self._parse_date(date_from)
        self.date_to = self._parse_date(date_to)
        self.locations = locations or []
        self.form_ids = form_ids or []
        self.field_filters = field_filters or {}
        self.exclude_incomplete = exclude_incomplete
        self.geo_fields = geo_fields or {
            "dimension_1": "location_name",  # Default to location_name field
            "dimension_2": None,
            "dimension_3": None,
        }
    
    @staticmethod
    def _parse_date(d: Optional[Any]) -> Optional[datetime]:
        """Parse date from various formats."""
        if d is None:
            return None
        
        if isinstance(d, datetime):
            return d
        
        if isinstance(d, date):
            return datetime.combine(d, datetime.min.time())
        
        if isinstance(d, str):
            try:
                return datetime.fromisoformat(d)
            except ValueError:
                try:
                    return datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Could not parse date: {d}")
                    return None
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging/caching."""
        return {
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "locations": [loc.to_dict() for loc in self.locations],
            "form_ids": self.form_ids,
            "field_filters": self.field_filters,
            "exclude_incomplete": self.exclude_incomplete,
        }
    
    def _get_jsonb_path_col(self, col: Any, path: str) -> Any:
        """Helper to build a JSONB path expression from a slash-separated path."""
        parts = path.replace(".", "/").split("/")
        expr = col
        for part in parts[:-1]:
            expr = expr.op("->")(part)
        return expr.op("->>")(parts[-1])

    def apply_to_query(self, query: Query) -> Query:
        """
        Apply filters to a SQLAlchemy query on Submission model.
        
        Returns filtered query.
        """
        conditions = []
        
        if self.date_from:
            conditions.append(Submission.created_at >= self.date_from)
        
        if self.date_to:
            date_to_end = self._parse_date(self.date_to)
            if date_to_end:
                from datetime import timedelta
                date_to_end = date_to_end + timedelta(days=1)
                conditions.append(Submission.created_at < date_to_end)
        
        if self.form_ids:
            conditions.append(Submission.form_id.in_(self.form_ids))
        
        if self.exclude_incomplete:
            # Use JSONB operator for performance if supported by DB
            conditions.append(Submission.cleaned_data.op('->')('_has_errors').astext.cast(bool) == False)
        
        # Optimize dimensions (Province, Region, District)
        if self.locations:
            location_conditions = []
            for loc in self.locations:
                if loc.is_empty():
                    continue
                
                loc_parts = []
                for dim_key, dim_val in [
                    ("dimension_1", loc.dimension_1),
                    ("dimension_2", loc.dimension_2),
                    ("dimension_3", loc.dimension_3)
                ]:
                    if dim_val and str(dim_val).lower() != "all":
                        field_name = self.geo_fields.get(dim_key)
                        if not field_name:
                            continue
                            
                        val = str(dim_val).lower().strip()
                        val_code = val.replace(" ", "_")
                        
                        if field_name == "location_name":
                            # Check both column and cleaned_data for dimension_1 if it's location_name
                            loc_parts.append(
                                or_(
                                    func.lower(Submission.location_name) == val,
                                    func.replace(func.lower(Submission.location_name), " ", "_") == val_code,
                                    func.lower(Submission.cleaned_data.op("->>")("location_name")) == val,
                                    func.replace(func.lower(Submission.cleaned_data.op("->>")("location_name")), " ", "_") == val_code
                                )
                            )
                        else:
                            # Handle nested JSONB paths
                            target_col = self._get_jsonb_path_col(Submission.cleaned_data, field_name)
                            loc_parts.append(
                                or_(
                                    func.lower(target_col) == val,
                                    func.replace(func.lower(target_col), " ", "_") == val_code
                                )
                            )
                
                if loc_parts:
                    location_conditions.append(and_(*loc_parts))
            
            if location_conditions:
                conditions.append(or_(*location_conditions))

        # Basic field filter optimization (supports nested fields)
        if self.field_filters:
            for field_name, filter_value in self.field_filters.items():
                if filter_value is None or filter_value == "" or filter_value == [] or (isinstance(filter_value, str) and filter_value.lower() == "all"):
                    continue
                
                # Soft-matching in SQL
                target_col = self._get_jsonb_path_col(Submission.cleaned_data, field_name)
                
                if isinstance(filter_value, list):
                    list_conditions = []
                    for fv in filter_value:
                        val = str(fv).lower().strip()
                        val_code = val.replace(" ", "_")
                        list_conditions.append(
                            or_(
                                func.lower(target_col) == val,
                                func.replace(func.lower(target_col), " ", "_") == val_code
                            )
                        )
                    if list_conditions:
                        conditions.append(or_(*list_conditions))
                else:
                    val = str(filter_value).lower().strip()
                    val_code = val.replace(" ", "_")
                    conditions.append(
                        or_(
                            func.lower(target_col) == val,
                            func.replace(func.lower(target_col), " ", "_") == val_code
                        )
                    )
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        return query
    
    def matches_submission(self, submission: Submission) -> bool:
        """
        Check if a single submission matches all filter criteria.
        
        Used for in-memory filtering when complex logic is needed.
        """
        payload = submission.cleaned_data or submission.submission_data or {}
        
        if not isinstance(payload, dict):
            return False
        
        if self.date_from and submission.created_at < self.date_from:
            return False
        
        if self.date_to:
            date_to_end = self._parse_date(self.date_to)
            if date_to_end:
                from datetime import timedelta
                date_to_end = date_to_end + timedelta(days=1)
                if submission.created_at >= date_to_end:
                    return False
        
        if self.form_ids and submission.form_id not in self.form_ids:
            return False
        
        if self.exclude_incomplete and payload.get("_has_errors"):
            return False
        
        if self.locations:
            location_match = False
            for loc in self.locations:
                if self._location_matches(payload, loc):
                    location_match = True
                    break
            if not location_match:
                return False
        
        if self.field_filters:
            for field_name, filter_value in self.field_filters.items():
                submission_value = get_nested_field_value(payload, field_name)
                
                if filter_value is None or filter_value == "" or filter_value == [] or (isinstance(filter_value, str) and filter_value.lower() == "all"):
                    continue
                
                # Normalize values for comparison: lowercase, strip, and replace spaces with underscores for code-matching
                def normalize(v: Any) -> str:
                    return str(v).lower().strip().replace(" ", "_")
                
                def soft_match(v1: Any, v2: Any) -> bool:
                    s1 = str(v1).lower().strip()
                    s2 = str(v2).lower().strip()
                    # Match exact, or underscored (code-like)
                    return s1 == s2 or s1.replace(" ", "_") == s2 or s1 == s2.replace(" ", "_")

                if isinstance(filter_value, list):
                    match_found = False
                    for fv in filter_value:
                        if soft_match(submission_value, fv):
                            match_found = True
                            break
                    if not match_found:
                        return False
                else:
                    if not soft_match(submission_value, filter_value):
                        return False
        
        return True
    
    def _location_matches(self, payload: Dict[str, Any], location: LocationFilter) -> bool:
        """Check if submission's location matches the filter."""
        if location.is_empty():
            return True
        
        def soft_match(v1: Any, v2: Any) -> bool:
            if v1 is None or v2 is None: return v1 == v2
            s1 = str(v1).lower().strip()
            s2 = str(v2).lower().strip()
            return s1 == s2 or s1.replace(" ", "_") == s2 or s1 == s2.replace(" ", "_")
        
        if location.dimension_1 and str(location.dimension_1).lower() != "all":
            field_name = self.geo_fields.get("dimension_1", "location_name")
            if field_name:
                value = get_nested_field_value(payload, field_name)
                if not soft_match(value, location.dimension_1):
                    return False
        
        if location.dimension_2 and str(location.dimension_2).lower() != "all":
            field_name = self.geo_fields.get("dimension_2")
            if field_name:
                value = get_nested_field_value(payload, field_name)
                if not soft_match(value, location.dimension_2):
                    return False
        
        if location.dimension_3 and str(location.dimension_3).lower() != "all":
            field_name = self.geo_fields.get("dimension_3")
            if field_name:
                value = get_nested_field_value(payload, field_name)
                if not soft_match(value, location.dimension_3):
                    return False
        
        return True
    
    def filter_submissions(self, submissions: List[Submission]) -> List[Submission]:
        """
        In-memory filter of submissions.
        
        Used when database-level filtering is insufficient.
        """
        return [sub for sub in submissions if self.matches_submission(sub)]
    
    def get_filter_hash(self) -> str:
        """Generate a hash of filter context for caching."""
        import hashlib
        import json
        
        filter_dict = self.to_dict()
        filter_json = json.dumps(filter_dict, sort_keys=True, default=str)
        return hashlib.sha256(filter_json.encode()).hexdigest()


class AggregationHelper:
    """Helper functions for common aggregations across submissions."""
    
    @staticmethod
    def count_by_field(
        submissions: List[Submission],
        field_name: str,
        include_null: bool = False
    ) -> Dict[str, int]:
        """
        Count submissions by field values.
        
        Returns: {field_value: count}
        """
        counts = {}
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            value = get_nested_field_value(payload, field_name)
            
            if value is None or value == "":
                if include_null:
                    counts["<null>"] = counts.get("<null>", 0) + 1
                continue
            
            value_str = str(value)
            counts[value_str] = counts.get(value_str, 0) + 1
        
        return counts
    
    @staticmethod
    def numeric_stats(
        submissions: List[Submission],
        field_name: str
    ) -> Dict[str, float]:
        """
        Compute statistics on numeric field.
        
        Returns: {min, max, mean, median, std_dev, count}
        """
        values = []
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            value = get_nested_field_value(payload, field_name)
            
            if value is None or value == "":
                continue
            
            try:
                numeric_value = float(value)
                values.append(numeric_value)
            except (ValueError, TypeError):
                continue
        
        if not values:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "std_dev": None,
                "count": 0,
            }
        
        values_sorted = sorted(values)
        count = len(values)
        
        import statistics
        mean = statistics.mean(values)
        median = statistics.median(values)
        std_dev = statistics.stdev(values) if count > 1 else 0
        
        return {
            "min": values_sorted[0],
            "max": values_sorted[-1],
            "mean": round(mean, 2),
            "median": median,
            "std_dev": round(std_dev, 2),
            "count": count,
        }
    
    @staticmethod
    def cross_tabulation(
        submissions: List[Submission],
        field_1: str,
        field_2: str
    ) -> List[Dict[str, Any]]:
        """
        Cross-tabulate two fields.
        
        Returns: [{dimension1, dimension2, count}]
        """
        counts = {}
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            value_1 = get_nested_field_value(payload, field_1)
            value_2 = get_nested_field_value(payload, field_2)
            
            if value_1 is None or value_1 == "" or value_2 is None or value_2 == "":
                continue
            
            key = (str(value_1), str(value_2))
            counts[key] = counts.get(key, 0) + 1
        
        return [
            {
                "dimension1": key[0],
                "dimension2": key[1],
                "count": count
            }
            for key, count in sorted(counts.items())
        ]
    
    @staticmethod
    def percentage_breakdown(
        submissions: List[Submission],
        field_name: str,
        target_value: Any
    ) -> float:
        """
        Calculate percentage of submissions where field == target_value.
        
        Returns: percentage (0-100)
        """
        if not submissions:
            return 0.0
        
        count = 0
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            value = get_nested_field_value(payload, field_name)
            
            if str(value) == str(target_value):
                count += 1
        
        return (count / len(submissions)) * 100.0
