"""Report Service - Orchestrates all report generation."""
import logging
import hashlib
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Form as FormModel, Submission, KPIValue, ReportCache, FormFieldMapping
from report_filters import FilterContext, LocationFilter, AggregationHelper, get_nested_field_value
from kpi_engine import KPIEngine

logger = logging.getLogger(__name__)


class ReportService:
    """
    Main service for generating all report types.
    Orchestrates filters, KPI computation, and aggregations.
    """
    
    def __init__(self, db: Session):
        """Initialize report service."""
        self.db = db
        self.kpi_engine = KPIEngine(db)
    
    def get_survey_summary(
        self,
        form_id: int,
        filters_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate survey summary report.
        
        Includes: total submissions, completion rate, question-wise summaries.
        """
        context = self._build_context(filters_request, [form_id])
        form = self.db.query(FormModel).filter(FormModel.id == form_id).first()
        
        if not form:
            return {"error": "Form not found"}
        
        submissions_query = self.db.query(Submission).filter(Submission.form_id == form_id)
        submissions_query = context.apply_to_query(submissions_query)
        submissions = submissions_query.all()
        
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("survey_summary", context, 0, 0),
                "form_id": form_id,
                "form_title": form.title,
                "summary": {
                    "total_submissions": 0,
                    "completion_rate": 0.0,
                    "validation_rate": 0.0,
                    "date_range": None,
                },
                "question_summaries": [],
            }
        
        summary = {
            "total_submissions": len(submissions),
            "completion_rate": self._calculate_completion_rate(submissions),
            "validation_rate": self._calculate_validation_rate(submissions),
            "date_range": {
                "from": min(s.created_at for s in submissions).isoformat() if submissions else None,
                "to": max(s.created_at for s in submissions).isoformat() if submissions else None,
            }
        }
        
        question_summaries = self._generate_question_summaries(form, submissions)
        
        return {
            "metadata": self._build_metadata("survey_summary", context, len(submissions), len(submissions)),
            "form_id": form_id,
            "form_title": form.title,
            "summary": summary,
            "question_summaries": question_summaries,
        }
    
    def get_indicator_report(
        self,
        filters_request: Dict[str, Any],
        kpi_codes: Optional[List[str]] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate indicator/KPI report.
        
        Computes all KPIs (or specified ones) with current values, targets, and trends.
        """
        context = self._build_context(filters_request)
        
        submissions = self.db.query(Submission)
        submissions = context.apply_to_query(submissions).all()
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("indicators", context, 0, 0),
                "kpis": [],
                "by_category": {},
            }
        
        kpis = self.kpi_engine.compute_all(submissions, context, category=category)
        
        if kpi_codes:
            kpis = [kpi for kpi in kpis if kpi.kpi_code in kpi_codes]
        
        by_category = {}
        for kpi in kpis:
            cat = kpi.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(kpi.to_dict())
        
        return {
            "metadata": self._build_metadata("indicators", context, len(submissions), len(submissions)),
            "kpis": [kpi.to_dict() for kpi in kpis],
            "by_category": by_category,
            "highlights": self._identify_highlights(kpis),
        }
    
    def get_demographics(
        self,
        filters_request: Dict[str, Any],
        form_id: Optional[int] = None,
        age_field: Optional[str] = None,
        gender_field: Optional[str] = None,
        hh_size_field: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate demographics report.
        
        Dynamically discovers demographic fields from form schema or mapping.
        Includes age, gender, household size distributions (if applicable to form).
        
        Args:
            filters_request: Filter parameters
            form_id: Specific form to analyze (optional, uses mapping if available)
            age_field: Override age field name
            gender_field: Override gender field name
            hh_size_field: Override household size field name
        """
        context = self._build_context(filters_request)
        
        submissions = self.db.query(Submission)
        submissions = context.apply_to_query(submissions).all()
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("demographics", context, 0, 0),
                "demographics": {},
            }
        
        # Determine which form(s) we're analyzing
        form_ids = form_id and [form_id] or [s.form_id for s in submissions]
        
        # Get field mappings from database or auto-discover from schema
        field_map = self._discover_demographic_fields(
            form_ids[0] if form_ids else None,
            age_field, gender_field, hh_size_field,
            submissions
        )
        
        demographics = {}
        
        if field_map.get("age_field"):
            demographics["by_age"] = self._age_distribution(submissions, field_map["age_field"])
        
        if field_map.get("gender_field"):
            demographics["by_gender"] = self._gender_distribution(submissions, field_map["gender_field"])
        
        if field_map.get("hh_size_field"):
            demographics["by_hh_size"] = AggregationHelper.numeric_stats(submissions, field_map["hh_size_field"])
        
        if field_map.get("gender_field") and field_map.get("age_field"):
            cross_tab = AggregationHelper.cross_tabulation(
                submissions,
                field_map["gender_field"],
                field_map["age_field"]
            )
            if cross_tab:
                demographics["cross_tabulation"] = cross_tab
        
        return {
            "metadata": self._build_metadata("demographics", context, len(submissions), len(submissions)),
            "demographics": demographics,
        }
    
    def get_geospatial(
        self,
        filters_request: Dict[str, Any],
        form_id: Optional[int] = None,
        location_field: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate geospatial report.
        
        Dynamically discovers location field from form mapping or schema.
        Includes GPS points, heatmap data, coverage by location.
        
        Args:
            filters_request: Filter parameters
            form_id: Specific form to analyze (optional)
            location_field: Override location field name
        """
        context = self._build_context(filters_request)
        
        submissions = self.db.query(Submission)
        submissions = context.apply_to_query(submissions).all()
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("geo", context, 0, 0),
                "points": [],
                "coverage": {},
                "bounds": {},
            }
        
        form_ids = form_id and [form_id] or list(set([s.form_id for s in submissions]))
        
        if not location_field and form_ids:
            mapping = self.db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form_ids[0]).first()
            if mapping and mapping.location_field:
                location_field = mapping.location_field
        
        points = []
        seen_locations = set()
        location_submissions = {}
        
        for sub in submissions:
            if sub.location_lat and sub.location_lng:
                key = (sub.location_lat, sub.location_lng)
                if key not in location_submissions:
                    location_submissions[key] = {
                        "submissions": [],
                        "lat": sub.location_lat,
                        "lng": sub.location_lng,
                        "location_name": sub.location_name,
                    }
                location_submissions[key]["submissions"].append(sub.id)
        
        for key, location_data in location_submissions.items():
            points.append({
                "lat": location_data["lat"],
                "lng": location_data["lng"],
                "count": len(location_data["submissions"]),
                "location_name": location_data["location_name"],
                "submissions": location_data["submissions"],
            })
        
        coverage = self._calculate_coverage(submissions, location_field or "location_name")
        bounds = self._calculate_bounds(submissions)
        
        return {
            "metadata": self._build_metadata("geo", context, len(submissions), len(submissions)),
            "points": points,
            "coverage": coverage,
            "bounds": bounds,
        }
    
    def get_trends(
        self,
        kpi_code: str,
        filters_request: Dict[str, Any],
        granularity: str = "monthly",
    ) -> Dict[str, Any]:
        """
        Generate trend report for a KPI.
        
        Shows KPI values over time with specified granularity.
        """
        context = self._build_context(filters_request)
        
        submissions = self.db.query(Submission)
        submissions = context.apply_to_query(submissions).all()
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("trends", context, 0, 0),
                "kpi_code": kpi_code,
                "kpi_label": "Unknown",
                "time_granularity": granularity,
                "trend_data": [],
                "summary": {},
            }
        
        kpi_def = self.kpi_engine.get_kpi_definition(kpi_code)
        if not kpi_def:
            return {"error": f"KPI not found: {kpi_code}"}
        
        trend_data = self.kpi_engine.compute_time_series(kpi_code, submissions, granularity)
        
        return {
            "metadata": self._build_metadata("trends", context, len(submissions), len(submissions)),
            "kpi_code": kpi_code,
            "kpi_label": kpi_def.label,
            "time_granularity": granularity,
            "trend_data": trend_data,
            "summary": self._summarize_trend(trend_data),
        }
    
    def get_program_comparison(
        self,
        dimension: str,
        kpi_codes: List[str],
        filters_request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate program comparison report.
        
        Compares KPIs across different programs/locations/forms.
        """
        context = self._build_context(filters_request)
        
        submissions = self.db.query(Submission)
        submissions = context.apply_to_query(submissions).all()
        submissions = context.filter_submissions(submissions)
        
        if not submissions:
            return {
                "metadata": self._build_metadata("program_comparison", context, 0, 0),
                "comparison_dimension": dimension,
                "kpi_code": kpi_codes[0] if kpi_codes else None,
                "items": [],
                "aggregate": {},
            }
        
        kpi_code = kpi_codes[0] if kpi_codes else None
        if not kpi_code:
            return {"error": "No KPI specified"}
        
        grouped_submissions = self._group_submissions(submissions, dimension)
        
        items = []
        kpi_values = []
        
        for item_id, item_label, item_subs in grouped_submissions:
            result = self.kpi_engine.compute(kpi_code, item_subs)
            if result:
                status = self._determine_status(result)
                items.append({
                    "item_id": item_id,
                    "item_label": item_label,
                    "kpi_value": result.value,
                    "target": result.target,
                    "baseline": result.baseline,
                    "sample_size": result.sample_size,
                    "status": status,
                })
                kpi_values.append(result.value)
        
        aggregate = self._calculate_aggregate(kpi_values)
        
        return {
            "metadata": self._build_metadata("program_comparison", context, len(submissions), len(submissions)),
            "comparison_dimension": dimension,
            "kpi_code": kpi_code,
            "items": items,
            "aggregate": aggregate,
        }
    
    def _build_context(
        self,
        filters_request: Dict[str, Any],
        form_ids: Optional[List[int]] = None
    ) -> FilterContext:
        """Build FilterContext from request dict."""
        locations = []
        for loc_dict in filters_request.get("locations", []):
            locations.append(LocationFilter(
                dimension_1=loc_dict.get("dimension_1"),
                dimension_2=loc_dict.get("dimension_2"),
                dimension_3=loc_dict.get("dimension_3"),
            ))
        
        return FilterContext(
            date_from=filters_request.get("date_from"),
            date_to=filters_request.get("date_to"),
            locations=locations,
            form_ids=form_ids or filters_request.get("form_ids", []),
            field_filters=filters_request.get("field_filters", {}),
            exclude_incomplete=filters_request.get("exclude_incomplete", False),
        )
    
    def _build_metadata(
        self,
        report_type: str,
        context: FilterContext,
        total_analyzed: int,
        total_filtered: int
    ) -> Dict[str, Any]:
        """Build report metadata."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "report_type": report_type,
            "filters_applied": context.to_dict(),
            "total_submissions_analyzed": total_analyzed,
            "total_submissions_in_filter": total_filtered,
            "data_quality_pct": 100.0,  # Placeholder
        }
    
    def _calculate_completion_rate(self, submissions: List[Submission]) -> float:
        """Calculate percentage of complete submissions."""
        if not submissions:
            return 0.0
        
        complete = sum(1 for s in submissions if s.cleaned_data and not s.cleaned_data.get("_has_errors"))
        return (complete / len(submissions)) * 100.0
    
    def _calculate_validation_rate(self, submissions: List[Submission]) -> float:
        """Calculate percentage of submissions with valid data."""
        if not submissions:
            return 0.0
        
        valid = sum(1 for s in submissions if not s.cleaned_data or not s.cleaned_data.get("_has_errors"))
        return (valid / len(submissions)) * 100.0
    
    def _generate_question_summaries(
        self,
        form: FormModel,
        submissions: List[Submission]
    ) -> List[Dict[str, Any]]:
        """Generate summaries for each question in the form."""
        summaries = []
        
        form_schema = form.form_schema or {}
        survey = form_schema.get("content", {}).get("survey", [])
        
        for question in survey[:10]:
            field_name = question.get("name")
            if not field_name:
                continue
            
            field_type = question.get("type", "text")
            field_label = question.get("label", [field_name])
            if isinstance(field_label, list) and field_label:
                field_label = field_label[0]
            
            counts = AggregationHelper.count_by_field(submissions, field_name, include_null=True)
            valid_responses = sum(v for k, v in counts.items() if k != "<null>")
            null_responses = counts.get("<null>", 0)
            
            if field_type in ["select_one", "select_multiple"]:
                options = [
                    {
                        "label": str(k),
                        "code": str(k),
                        "count": v,
                        "percentage": (v / max(len(submissions), 1)) * 100.0,
                    }
                    for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
                    if k != "<null>"
                ]
                
                summary = {
                    "field": field_name,
                    "field_label": str(field_label),
                    "field_type": field_type,
                    "response_type": "categorical",
                    "valid_responses": valid_responses,
                    "null_responses": null_responses,
                    "options": options,
                }
            else:
                stats = AggregationHelper.numeric_stats(submissions, field_name) if "integer" in field_type or "decimal" in field_type else None
                
                summary = {
                    "field": field_name,
                    "field_label": str(field_label),
                    "field_type": field_type,
                    "response_type": "numeric" if stats else "text",
                    "valid_responses": valid_responses,
                    "null_responses": null_responses,
                    "statistics": stats,
                }
            
            summaries.append(summary)
        
        return summaries
    
    def _age_distribution(self, submissions: List[Submission], age_field: str) -> List[Dict[str, Any]]:
        """Generate age distribution by age groups."""
        age_groups = {
            "0-5": (0, 5),
            "6-17": (6, 17),
            "18-60": (18, 60),
            "60+": (60, 150),
        }
        
        distribution = {group: 0 for group in age_groups}
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            age_val = get_nested_field_value(payload, age_field)
            
            if age_val is None or age_val == "":
                continue
            
            try:
                age = int(float(age_val))
                for group, (min_age, max_age) in age_groups.items():
                    if min_age <= age <= max_age:
                        distribution[group] += 1
                        break
            except (ValueError, TypeError):
                continue
        
        total = sum(distribution.values())
        return [
            {
                "age_group": group,
                "count": count,
                "percentage": (count / total * 100.0) if total > 0 else 0.0,
            }
            for group, count in distribution.items()
        ]
    
    def _gender_distribution(self, submissions: List[Submission], gender_field: str) -> List[Dict[str, Any]]:
        """Generate gender distribution."""
        counts = AggregationHelper.count_by_field(submissions, gender_field)
        total = sum(counts.values())
        
        return [
            {
                "gender": str(gender),
                "count": count,
                "percentage": (count / total * 100.0) if total > 0 else 0.0,
            }
            for gender, count in sorted(counts.items())
        ]
    
    def _calculate_coverage(self, submissions: List[Submission], location_field: str) -> Dict[str, Any]:
        """Calculate coverage by location."""
        location_counts = AggregationHelper.count_by_field(submissions, location_field)
        total = sum(location_counts.values())
        
        return {
            "by_location": [
                {
                    "location": str(loc),
                    "submissions": count,
                    "coverage_pct": (count / total * 100.0) if total > 0 else 0.0,
                }
                for loc, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
            ]
        }
    
    def _calculate_bounds(self, submissions: List[Submission]) -> Dict[str, float]:
        """Calculate geographic bounds from GPS data."""
        lats = [s.location_lat for s in submissions if s.location_lat]
        lngs = [s.location_lng for s in submissions if s.location_lng]
        
        if not lats or not lngs:
            return {}
        
        return {
            "north": max(lats),
            "south": min(lats),
            "east": max(lngs),
            "west": min(lngs),
        }
    
    def _identify_highlights(self, kpis) -> List[Dict[str, Any]]:
        """Identify notable findings from KPIs."""
        highlights = []
        
        for kpi in kpis:
            if kpi.target and kpi.value >= kpi.target:
                highlights.append({
                    "type": "target_achieved",
                    "kpi_code": kpi.kpi_code,
                    "message": f"{kpi.label} has reached its target of {kpi.target}{kpi.unit}",
                })
            elif kpi.baseline and kpi.value < kpi.baseline * 0.9:
                highlights.append({
                    "type": "declining",
                    "kpi_code": kpi.kpi_code,
                    "message": f"{kpi.label} has declined below 90% of baseline",
                })
        
        return highlights[:5]
    
    def _summarize_trend(self, trend_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize trend data."""
        values = [t["value"] for t in trend_data if t["value"] is not None]
        
        if not values or len(values) < 2:
            return {
                "overall_trend": "no_data",
                "trend_pct_change": 0.0,
                "avg_improvement": 0.0,
            }
        
        first_value = values[0]
        last_value = values[-1]
        pct_change = ((last_value - first_value) / first_value * 100.0) if first_value != 0 else 0.0
        
        trend = "up" if pct_change > 1 else "down" if pct_change < -1 else "stable"
        
        return {
            "overall_trend": trend,
            "trend_pct_change": round(pct_change, 2),
            "avg_improvement": round(sum(values) / len(values), 2),
        }
    
    def _determine_status(self, result) -> str:
        """Determine status relative to target."""
        if result.target is None:
            return "no_data"
        
        if result.value >= result.target:
            return "ahead"
        
        if result.baseline is not None:
            progress = (result.value - result.baseline) / (result.target - result.baseline)
            if progress >= 0.5:
                return "on_track"
        
        return "behind"
    
    def _group_submissions(
        self,
        submissions: List[Submission],
        dimension: str
    ) -> List[tuple]:
        """Group submissions by dimension."""
        grouped = {}
        
        if dimension == "form_id":
            for sub in submissions:
                form_id = sub.form_id
                if form_id not in grouped:
                    form = self.db.query(FormModel).filter(FormModel.id == form_id).first()
                    label = form.title if form else f"Form {form_id}"
                    grouped[form_id] = (form_id, label, [])
                grouped[form_id][2].append(sub)
        else:
            for sub in submissions:
                payload = sub.cleaned_data or sub.submission_data or {}
                value = get_nested_field_value(payload, dimension)
                
                if value is None:
                    value = "<undefined>"
                
                value_str = str(value)
                if value_str not in grouped:
                    grouped[value_str] = (value_str, value_str, [])
                grouped[value_str][2].append(sub)
        
        return list(grouped.values())
    
    def _calculate_aggregate(self, values: List[float]) -> Dict[str, float]:
        """Calculate aggregate statistics."""
        if not values:
            return {}
        
        import statistics
        
        return {
            "avg": round(statistics.mean(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "median": round(statistics.median(values), 2),
        }
    
    def _discover_demographic_fields(
        self,
        form_id: Optional[int],
        age_field: Optional[str],
        gender_field: Optional[str],
        hh_size_field: Optional[str],
        submissions: List[Submission]
    ) -> Dict[str, Optional[str]]:
        """
        Discover demographic field names from form mapping or schema.
        
        Priority:
        1. Explicit parameters (overrides)
        2. FormFieldMapping from database
        3. Auto-detect from form schema
        4. Return empty map if fields don't exist
        """
        result = {
            "age_field": age_field,
            "gender_field": gender_field,
            "hh_size_field": hh_size_field,
        }
        
        if not form_id:
            return result
        
        form = self.db.query(FormModel).filter(FormModel.id == form_id).first()
        if not form:
            return result
        
        mapping = self.db.query(FormFieldMapping).filter(FormFieldMapping.form_id == form_id).first()
        
        if mapping:
            if not result["age_field"]:
                result["age_field"] = mapping.age_field
            if not result["gender_field"]:
                result["gender_field"] = mapping.gender_field
            if not result["hh_size_field"]:
                result["hh_size_field"] = mapping.household_size_field
        
        if (not result["age_field"] or not result["gender_field"]) and form.form_schema:
            discovered = self._auto_detect_fields(form.form_schema, submissions)
            
            if not result["age_field"]:
                result["age_field"] = discovered.get("age_field")
            if not result["gender_field"]:
                result["gender_field"] = discovered.get("gender_field")
            if not result["hh_size_field"]:
                result["hh_size_field"] = discovered.get("hh_size_field")
        
        return result
    
    def _auto_detect_fields(
        self,
        form_schema: Dict[str, Any],
        submissions: List[Submission]
    ) -> Dict[str, Optional[str]]:
        """
        Auto-detect demographic fields from form schema by looking for keywords.
        
        Works for Child Protection & Education forms with any field names.
        """
        result = {
            "age_field": None,
            "gender_field": None,
            "hh_size_field": None,
        }
        
        survey = form_schema.get("content", {}).get("survey", [])
        
        age_keywords = ["age", "dob", "birth", "years"]
        gender_keywords = ["gender", "sex", "male", "female"]
        hh_keywords = ["household", "family", "members", "size"]
        
        for question in survey:
            name = question.get("name", "").lower()
            label = str(question.get("label", "")).lower()
            
            if not result["age_field"]:
                for keyword in age_keywords:
                    if keyword in name or keyword in label:
                        result["age_field"] = question.get("name")
                        break
            
            if not result["gender_field"]:
                for keyword in gender_keywords:
                    if keyword in name or keyword in label:
                        result["gender_field"] = question.get("name")
                        break
            
            if not result["hh_size_field"]:
                for keyword in hh_keywords:
                    if keyword in name or keyword in label:
                        result["hh_size_field"] = question.get("name")
                        break
        
        if result["hh_size_field"]:
            has_numeric = self._field_is_numeric(submissions, result["hh_size_field"])
            if not has_numeric:
                result["hh_size_field"] = None
        
        return result
    
    def _field_is_numeric(self, submissions: List[Submission], field_name: str) -> bool:
        """Check if field contains numeric values in at least 50% of submissions."""
        if not submissions:
            return False
        
        numeric_count = 0
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            value = get_nested_field_value(payload, field_name)
            
            if value is None or value == "":
                continue
            
            try:
                float(value)
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        
        return numeric_count >= len(submissions) * 0.5
