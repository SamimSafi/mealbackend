import logging
import hashlib
import json
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text, String, cast, or_, literal
from models import Submission, Form as FormModel, ReportCache
from schemas import CrossTabResponse, StackedBarResponse, StackedBarItem, AnalysisFiltersResponse, AnalysisReportResponse
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def _get_json_field(self, field_path: str):
        """Returns the SQL expression to extract a JSON field, unquoted if necessary."""
        if not field_path:
            return None
            
        # For keys with slashes, we must use quoted path syntax: $."path/to/field"
        # This works for both SQLite and MySQL
        json_path = f'$."{field_path}"'
        
        dialect = self.db.bind.dialect.name
        if dialect == 'mysql':
            return func.json_unquote(func.json_extract(Submission.cleaned_data, json_path))
        else:
            return func.json_extract(Submission.cleaned_data, json_path)

    def _apply_filters(
        self, 
        query, 
        form_id: str, 
        date_from: Optional[date] = None, 
        date_to: Optional[date] = None, 
        location: Optional[str] = None, 
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None
    ):
        # Find the internal form_id - support both internal ID and Kobo Form ID
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
            
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")
        
        query = query.filter(Submission.form_id == form.id)

        if date_from:
            query = query.filter(Submission.created_at >= date_from)
        if date_to:
            query = query.filter(Submission.created_at <= date_to)
        
        if location:
            query = query.filter(Submission.location_name == location)
            
        if enumerator:
            enum_attr = self._get_json_field("_submitted_by")
            query = query.filter(enum_attr == enumerator)

        if filter_field and filter_value:
            f_attr = self._get_json_field(filter_field)
            if f_attr is not None:
                query = query.filter(f_attr == filter_value)
            
        return query, form.id

    def _get_cache(self, report_type: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieve cached report result."""
        filters_hash = hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()
        cache = self.db.query(ReportCache).filter(
            ReportCache.report_type == report_type,
            ReportCache.filters_hash == filters_hash,
            ReportCache.expires_at > datetime.utcnow()
        ).first()
        
        if cache:
            cache.hit_count += 1
            self.db.commit()
            return cache.result_json
        return None

    def _set_cache(self, report_type: str, filters: Dict[str, Any], result: Dict[str, Any], form_id: Optional[int] = None):
        """Store report result in cache."""
        filters_hash = hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()
        
        # Delete old cache if exists
        self.db.query(ReportCache).filter(
            ReportCache.report_type == report_type,
            ReportCache.filters_hash == filters_hash
        ).delete()
        
        cache = ReportCache(
            report_type=report_type,
            filters_hash=filters_hash,
            form_id=form_id,
            result_json=result,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.db.add(cache)
        self.db.commit()

    def _get_full_path_mapping(self, form: FormModel) -> Dict[str, str]:
        """
        Smart mapping that connects short/common names to actual JSON paths.
        1. Maps full paths.
        2. Maps last part of path (e.g., 'province' -> 'info/province').
        3. Maps lowercase labels to paths (e.g., 'gender' -> 'beneficiary/sex').
        """
        sample = self.db.query(Submission.cleaned_data).filter(
            Submission.form_id == form.id
        ).first()
        
        mapping = {}
        
        # 1. Map from actual data keys
        if sample and sample[0]:
            for key in sample[0].keys():
                mapping[key.lower()] = key
                # Map short names (e.g., 'province' matches 'info/province')
                parts = key.split('/')
                mapping[parts[-1].lower()] = key
                # Map names without 'e5w_' or similar prefixes if they exist
                clean_short = parts[-1].replace('e5w_', '').replace('sls_', '')
                mapping[clean_short.lower()] = key

        # 2. Map from Form Schema Labels
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            for q in survey:
                q_name = q.get("name")
                if not q_name: continue
                
                # Resolve the full path for this question name if possible
                full_path = q_name
                for k in mapping.values():
                    if k.endswith(q_name):
                        full_path = k
                        break
                
                label = q.get("label", "")
                if isinstance(label, list) and label:
                    label = label[0]
                
                if label and isinstance(label, str):
                    # Map the label itself (e.g., "Province" -> "info/province")
                    mapping[label.lower().strip()] = full_path
                    # Map the label with underscores
                    mapping[label.lower().replace(' ', '_')] = full_path

        return mapping

    def _resolve_field(self, field_name: Optional[str], mapping: Dict[str, str]) -> Optional[str]:
        if not field_name:
            return None
        
        # Clean the input name (e.g., 'info/province' -> 'province')
        clean_input = field_name.lower().strip().split('/')[-1]
        
        # Try exact match first
        if field_name.lower() in mapping:
            return mapping[field_name.lower()]
        
        # Try the cleaned short name
        if clean_input in mapping:
            return mapping[clean_input]
            
        # Try removing common prefixes from input
        very_clean = clean_input.replace('e5w_', '').replace('sls_', '')
        if very_clean in mapping:
            return mapping[very_clean]
            
        return field_name

    def get_analysis_filters(self, form_id: str) -> AnalysisFiltersResponse:
        """Get available filters for a form."""
        cached = self._get_cache("analysis_filters", {"form_id": form_id})
        if cached:
            return AnalysisFiltersResponse(**cached)

        # Get form
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        # 1. Categorical fields from schema
        categorical_fields = []
        path_mapping = self._get_full_path_mapping(form)
        
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            for q in survey:
                q_type = q.get("type", "")
                if q_type in ["select_one", "text"]:
                    short_name = q.get("name")
                    full_path = path_mapping.get(short_name, short_name)
                    categorical_fields.append({
                        "name": full_path,
                        "label": q.get("label", [short_name])[0] if isinstance(q.get("label"), list) else q.get("label", short_name)
                    })

        # 2. Locations
        locations = self.db.query(Submission.location_name).filter(
            Submission.form_id == form.id,
            Submission.location_name.isnot(None),
            Submission.location_name != ""
        ).distinct().all()
        location_list = sorted([l[0] for l in locations])

        # 3. Enumerators
        enum_attr = self._get_json_field("_submitted_by")
        enumerator_list = []
        if enum_attr is not None:
            enumerators = self.db.query(enum_attr).filter(
                Submission.form_id == form.id,
                enum_attr.isnot(None)
            ).distinct().all()
            enumerator_list = sorted([e[0] for e in enumerators if e[0]])

        # 4. Date range
        date_stats = self.db.query(
            func.min(Submission.created_at),
            func.max(Submission.created_at)
        ).filter(Submission.form_id == form.id).first()
        
        date_range = {
            "min": date_stats[0].isoformat() if date_stats and date_stats[0] else None,
            "max": date_stats[1].isoformat() if date_stats and date_stats[1] else None
        }

        response = AnalysisFiltersResponse(
            categorical_fields=categorical_fields,
            locations=location_list,
            enumerators=enumerator_list,
            date_range=date_range
        )
        
        self._set_cache("analysis_filters", {"form_id": form_id}, response.model_dump(), form.id)
        return response

    def get_crosstab(
        self,
        form_id: str,
        row_field: Optional[str] = None,
        col_field: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None
    ) -> CrossTabResponse:
        # 0. Find internal form ID first to resolve paths
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")
            
        # Resolve field paths
        path_mapping = self._get_full_path_mapping(form)
        row_field = self._resolve_field(row_field, path_mapping)
        col_field = self._resolve_field(col_field, path_mapping)
        filter_field = self._resolve_field(filter_field, path_mapping)

        # 1. Total Responses (Filtered by metadata but NOT by categorical selection)
        base_query = self.db.query(func.count(Submission.id))
        base_query, _ = self._apply_filters(
            base_query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )
        total_responses = base_query.scalar() or 0

        filters = {
            "form_id": form_id,
            "row": row_field,
            "col": col_field,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "location": location,
            "enumerator": enumerator,
            "filter_field": filter_field,
            "filter_value": filter_value
        }
        
        cached = self._get_cache("crosstab", filters)
        if cached:
            return CrossTabResponse(**cached)

        # 2. Aggregated Counts
        row_attr = self._get_json_field(row_field) if row_field else cast(literal("Total"), String)
        col_attr = self._get_json_field(col_field) if col_field else cast(literal("Count"), String)

        query = self.db.query(
            row_attr.label("row_val"),
            col_attr.label("col_val"),
            func.count().label("count")
        )

        query, _ = self._apply_filters(
            query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )

        # Filter out nulls for the matrix itself (only if fields are provided)
        if row_field:
            query = query.filter(row_attr.isnot(None), row_attr != "")
        if col_field:
            query = query.filter(col_attr.isnot(None), col_attr != "")
        
        query = query.group_by("row_val", "col_val")
        results = query.all()
        
        # 3. Calculate grand total and missing counts
        grand_total = sum(r.count for r in results)
        missing_count = total_responses - grand_total
        missing_percentage = round((missing_count / total_responses * 100), 2) if total_responses > 0 else 0.0

        if not results:
            row_labels = ["Total"] if not row_field else []
            col_labels = ["Count"] if not col_field else []
            return CrossTabResponse(
                rows=row_labels, columns=col_labels, data=[], 
                row_totals=[], column_totals=[], grand_total=0,
                total_responses=total_responses, missing_count=missing_count, missing_percentage=missing_percentage
            )

        row_labels = sorted(list(set(r.row_val for r in results if r.row_val is not None)))
        col_labels = sorted(list(set(r.col_val for r in results if r.col_val is not None)))
        
        matrix = [[0 for _ in range(len(col_labels))] for _ in range(len(row_labels))]
        row_map = {label: i for i, label in enumerate(row_labels)}
        col_map = {label: i for i, label in enumerate(col_labels)}
        
        for r in results:
            if r.row_val in row_map and r.col_val in col_map:
                matrix[row_map[r.row_val]][col_map[r.col_val]] = r.count
                
        row_totals = [sum(row) for row in matrix]
        column_totals = [sum(matrix[r][c] for r in range(len(row_labels))) for c in range(len(col_labels))]
        
        response = CrossTabResponse(
            rows=row_labels,
            columns=col_labels,
            data=matrix,
            row_totals=row_totals,
            column_totals=column_totals,
            grand_total=grand_total,
            total_responses=total_responses,
            missing_count=missing_count,
            missing_percentage=missing_percentage
        )
        
        self._set_cache("crosstab", filters, response.model_dump(), form.id)
        return response

    def get_analysis_report(
        self,
        form_id: str,
        row_field: Optional[str] = None,
        col_field: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None
    ) -> AnalysisReportResponse:
        """
        Unified endpoint returning both Crosstab and Stacked Bar data.
        """
        crosstab = self.get_crosstab(
            form_id=form_id,
            row_field=row_field,
            col_field=col_field,
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
            filter_field=filter_field,
            filter_value=filter_value
        )
        
        stacked_bar = self.get_stacked_bar(
            form_id=form_id,
            x_field=row_field,
            stack_field=col_field,
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
            filter_field=filter_field,
            filter_value=filter_value
        )
        
        return AnalysisReportResponse(
            crosstab=crosstab,
            stacked_bar=stacked_bar
        )

    def get_stacked_bar(
        self,
        form_id: str,
        x_field: Optional[str] = None,
        stack_field: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None
    ) -> StackedBarResponse:
        filters = {
            "form_id": form_id,
            "x": x_field,
            "stack": stack_field,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "location": location,
            "enumerator": enumerator,
            "filter_field": filter_field,
            "filter_value": filter_value
        }
        
        cached = self._get_cache("stacked_bar", filters)
        if cached:
            return StackedBarResponse(**cached)

        crosstab = self.get_crosstab(
            form_id=form_id,
            row_field=x_field,
            col_field=stack_field,
            date_from=date_from,
            date_to=date_to,
            location=location,
            enumerator=enumerator,
            filter_field=filter_field,
            filter_value=filter_value
        )
        
        items = []
        for i, row_label in enumerate(crosstab.rows):
            counts = {}
            percentages = {}
            row_total = crosstab.row_totals[i]
            
            for j, col_label in enumerate(crosstab.columns):
                count = crosstab.data[i][j]
                counts[col_label] = count
                percentages[col_label] = round((count / row_total * 100), 2) if row_total > 0 else 0
                
            items.append(StackedBarItem(
                category=row_label,
                values=counts,
                percentages=percentages,
                total=row_total
            ))
            
        response = StackedBarResponse(
            x_axis=crosstab.rows,
            stacks=crosstab.columns,
            items=items,
            total_responses=crosstab.total_responses,
            missing_count=crosstab.missing_count,
            missing_percentage=crosstab.missing_percentage
        )
        
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        self._set_cache("stacked_bar", filters, response.model_dump(), form.id if form else None)
        
        return response
