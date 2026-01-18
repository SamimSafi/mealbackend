import logging
import hashlib
import json
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text, String, cast, or_, literal
from models import Submission, Form as FormModel, ReportCache
from schemas import (
    CrossTabResponse, StackedBarResponse, StackedBarItem, 
    AnalysisFiltersResponse, AnalysisReportResponse,
    NumericSummaryResponse, NumericStatistics, NumericDistributionResponse, Distribution,
    OrdinalFieldOption, OrdinalFieldInfo, OrdinalFieldsResponse,
    OrdinalResponseItem, OrdinalAnalysisSummary, OrdinalAnalysisMetadata,
    OrdinalScaleAnalysisResponse, OrdinalBatchAnalysisRequest, OrdinalBatchAnalysisResponse,
    OrdinalTrendItem, OrdinalTrendsResponse,
    MultiSelectOption, MultiSelectAnalysisResponse,
    MultiSelectBatchRequest, MultiSelectBatchResponse,
    DetailedCrossTabResponse, CrossTabRowItem, CrossTabColumnItem, CrossTabTable, CrossTabMetadata,
    TimeSeriesDataPoint, TimeSeriesResponse
)
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

        # 1. Fields from schema categorized by type
        categorical_fields = []
        numeric_fields = []
        date_fields = []
        
        path_mapping = self._get_full_path_mapping(form)
        
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            for q in survey:
                q_type = q.get("type", "")
                short_name = q.get("name")
                if not short_name:
                    continue
                
                full_path = path_mapping.get(short_name, short_name)
                label = q.get("label", [short_name])[0] if isinstance(q.get("label"), list) else q.get("label", short_name)
                
                field_info = {
                    "name": full_path,
                    "label": label,
                    "type": q_type
                }
                
                if q_type in ["select_one", "select_multiple", "text"]:
                    categorical_fields.append(field_info)
                elif q_type in ["integer", "decimal"]:
                    numeric_fields.append(field_info)
                elif q_type in ["date", "datetime", "today", "start", "end"]:
                    date_fields.append(field_info)

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
            numeric_fields=numeric_fields,
            date_fields=date_fields,
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

    def get_time_series(
        self,
        form_id: str,
        date_from: date,
        date_to: date,
        group_by: str = "day"
    ) -> TimeSeriesResponse:
        """Analyze submission trends over time."""
        # Find form
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        # Retrieve data with dates
        query = self.db.query(Submission.created_at)
        query = query.filter(
            Submission.form_id == form.id,
            Submission.created_at >= date_from,
            Submission.created_at <= datetime.combine(date_to, datetime.max.time())
        )
        
        results = query.all()
        total_submissions = len(results)
        
        if not results:
            return TimeSeriesResponse(
                success=True,
                form_id=form.id,
                form_name=form.title,
                date_from=str(date_from),
                date_to=str(date_to),
                group_by=group_by,
                total_submissions=0,
                average_per_period=0.0,
                trend="stable",
                data=[],
                insights=["No submissions found for the selected period"]
            )

        df = pd.DataFrame([r[0] for r in results], columns=["date"])
        df["date"] = pd.to_datetime(df["date"])
        
        # Sort values by date
        df = df.sort_values("date")
        
        if group_by == "day":
            df["period"] = df["date"].dt.strftime("%Y-%m-%d")
            df["label"] = df["date"].dt.strftime("%b %d")
        elif group_by == "week":
            # Period is the start of the week (Monday)
            df["period"] = df["date"].dt.to_period("W-MON").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
            df["label"] = df["date"].dt.strftime("Week %U, %Y")
        elif group_by == "month":
            df["period"] = df["date"].dt.strftime("%Y-%m")
            df["label"] = df["date"].dt.strftime("%b %Y")
        elif group_by == "quarter":
            df["period"] = df["date"].dt.to_period("Q").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
            df["label"] = df["date"].dt.to_period("Q").apply(lambda r: f"Q{r.quarter} {r.year}")
        else:
            df["period"] = df["date"].dt.strftime("%Y-%m-%d")
            df["label"] = df["date"].dt.strftime("%b %d")

        # Aggregate counts
        # We need to preserve the order, so we group by period and keep the first label
        agg = df.groupby("period").agg(
            count=("date", "size"),
            label=("label", "first")
        ).reset_index()
        
        agg = agg.sort_values("period")
        
        # Calculate cumulative
        agg["cumulative"] = agg["count"].cumsum()
        
        data = []
        for _, row in agg.iterrows():
            data.append(TimeSeriesDataPoint(
                period=str(row["period"]),
                label=str(row["label"]),
                count=int(row["count"]),
                cumulative=int(row["cumulative"])
            ))
        
        average_per_period = round(total_submissions / len(data), 1) if data else 0.0
        
        # Calculate trend
        trend = "stable"
        if len(data) >= 2:
            mid = len(data) // 2
            first_half = data[:mid]
            second_half = data[mid:]
            
            first_avg = sum(d.count for d in first_half) / len(first_half)
            second_avg = sum(d.count for d in second_half) / len(second_half)
            
            if first_avg > 0:
                change = (second_avg - first_avg) / first_avg
                if change > 0.1:
                    trend = "increasing"
                elif change < -0.1:
                    trend = "decreasing"
            elif second_avg > 0:
                trend = "increasing"

        # Insights
        peak_period = max(data, key=lambda x: x.count)
        insights = [
            f"Peak submissions on {peak_period.label} ({peak_period.count} submissions)",
            f"Average of {average_per_period} submissions per {group_by}"
        ]
        
        return TimeSeriesResponse(
            success=True,
            form_id=form.id,
            form_name=form.title,
            date_from=str(date_from),
            date_to=str(date_to),
            group_by=group_by,
            total_submissions=total_submissions,
            average_per_period=average_per_period,
            trend=trend,
            data=data,
            insights=insights
        )

    def _generate_crosstab_insights(
        self,
        row_field: str,
        col_field: str,
        rows_data: List[Dict[str, Any]],
        grand_total: int
    ) -> List[str]:
        insights = []
        if not rows_data or grand_total == 0:
            return insights
        
        try:
            for row in rows_data:
                row_label = row.get("label", "")
                row_count = row.get("count", 0)
                columns = row.get("columns", [])
                
                if row_count == 0:
                    continue
                    
                for col in columns:
                    col_label = col.get("label", "")
                    col_percentage = col.get("percentage", 0)
                    col_count = col.get("count", 0)
                    
                    if col_percentage >= 40:
                        insight = f"{col_percentage}% of {row_label.lower()} respondents chose {col_label.lower()}"
                        insights.append(insight)
            
            max_row = max(rows_data, key=lambda x: x.get("count", 0), default=None)
            if max_row:
                max_label = max_row.get("label", "")
                max_count = max_row.get("count", 0)
                max_pct = (max_count / grand_total * 100) if grand_total > 0 else 0
                insight = f"{max_pct:.1f}% of all respondents were {max_label.lower()}"
                insights.append(insight)
            
            min_row = min(rows_data, key=lambda x: x.get("count", 0), default=None)
            if min_row and min_row != max_row:
                min_label = min_row.get("label", "")
                min_count = min_row.get("count", 0)
                if min_count > 0:
                    min_pct = (min_count / grand_total * 100) if grand_total > 0 else 0
                    insight = f"Smallest group: {min_label.lower()} with {min_pct:.1f}% of respondents"
                    insights.append(insight)
            
            if len(rows_data) > 1:
                disparities = []
                for i, row1 in enumerate(rows_data):
                    for row2 in rows_data[i+1:]:
                        for col1 in row1.get("columns", []):
                            for col2 in row2.get("columns", []):
                                if col1.get("label") == col2.get("label"):
                                    pct1 = col1.get("percentage", 0)
                                    pct2 = col2.get("percentage", 0)
                                    diff = abs(pct1 - pct2)
                                    if diff > 15:
                                        disparities.append({
                                            "label": col1.get("label"),
                                            "pct1": pct1,
                                            "pct2": pct2,
                                            "row1": row1.get("label"),
                                            "row2": row2.get("label"),
                                            "diff": diff
                                        })
                
                if disparities:
                    max_disparity = max(disparities, key=lambda x: x.get("diff", 0))
                    insight = f"Significant disparity in {max_disparity['label'].lower()}: {max_disparity['pct1']:.1f}% for {max_disparity['row1'].lower()} vs {max_disparity['pct2']:.1f}% for {max_disparity['row2'].lower()}"
                    insights.append(insight)
        
        except Exception as e:
            logger.warning(f"Error generating insights: {str(e)}")
        
        return insights[:5]

    def get_detailed_crosstab(
        self,
        form_id: str,
        row_field: str,
        column_field: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> DetailedCrossTabResponse:
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form with ID {form_id} not found")
        
        path_mapping = self._get_full_path_mapping(form)
        row_path = self._resolve_field(row_field, path_mapping)
        col_path = self._resolve_field(column_field, path_mapping)
        
        if not row_path:
            available = list(path_mapping.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Field '{row_field}' not found in form. Available fields: {available}"
            )
        
        if not col_path:
            available = list(path_mapping.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Field '{column_field}' not found in form. Available fields: {available}"
            )
        
        base_query = self.db.query(func.count(Submission.id)).filter(Submission.form_id == form.id)
        if date_from:
            base_query = base_query.filter(Submission.created_at >= date_from)
        if date_to:
            base_query = base_query.filter(Submission.created_at <= date_to)
        
        total_responses = base_query.scalar() or 0
        
        row_attr = self._get_json_field(row_path)
        col_attr = self._get_json_field(col_path)
        
        query = self.db.query(
            row_attr.label("row_val"),
            col_attr.label("col_val"),
            func.count().label("count")
        ).filter(
            Submission.form_id == form.id,
            row_attr.isnot(None),
            row_attr != "",
            col_attr.isnot(None),
            col_attr != ""
        )
        
        if date_from:
            query = query.filter(Submission.created_at >= date_from)
        if date_to:
            query = query.filter(Submission.created_at <= date_to)
        
        query = query.group_by("row_val", "col_val")
        results = query.all()
        
        grand_total = sum(r.count for r in results)
        excluded_count = total_responses - grand_total
        
        row_labels = sorted(list(set(r.row_val for r in results if r.row_val)))
        col_labels = sorted(list(set(r.col_val for r in results if r.col_val)))
        
        row_map = {label: i for i, label in enumerate(row_labels)}
        col_map = {label: i for i, label in enumerate(col_labels)}
        
        matrix = [[0 for _ in range(len(col_labels))] for _ in range(len(row_labels))]
        
        for r in results:
            if r.row_val in row_map and r.col_val in col_map:
                matrix[row_map[r.row_val]][col_map[r.col_val]] = r.count
        
        column_totals_dict = {}
        rows_data = []
        
        for i, row_label in enumerate(row_labels):
            row_total = sum(matrix[i])
            columns_data = []
            
            for j, col_label in enumerate(col_labels):
                count = matrix[i][j]
                percentage = (count / row_total * 100) if row_total > 0 else 0.0
                columns_data.append(CrossTabColumnItem(
                    label=col_label,
                    count=count,
                    percentage=round(percentage, 1)
                ))
                
                if col_label not in column_totals_dict:
                    column_totals_dict[col_label] = 0
                column_totals_dict[col_label] += count
            
            rows_data.append(CrossTabRowItem(
                label=row_label,
                count=row_total,
                columns=columns_data
            ))
        
        insights = self._generate_crosstab_insights(row_field, column_field, 
                                                    [r.model_dump() for r in rows_data], grand_total)
        
        table = CrossTabTable(
            rows=rows_data,
            column_totals=column_totals_dict,
            grand_total=grand_total
        )
        
        metadata = CrossTabMetadata(
            generated_at=datetime.utcnow(),
            date_filter_applied=date_from is not None or date_to is not None,
            form_name=form.title
        )
        
        internal_form_id = form.id
        
        return DetailedCrossTabResponse(
            success=True,
            form_id=internal_form_id,
            row_field=row_field,
            column_field=column_field,
            total_responses=total_responses,
            excluded_count=excluded_count,
            table=table,
            insights=insights,
            metadata=metadata
        )

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

    def get_numeric_summary(
        self,
        form_id: str,
        field: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
        allow_negative: bool = False
    ) -> NumericSummaryResponse:
        """
        Calculate summary statistics for a numeric field.
        """
        # 0. Find internal form ID first to resolve paths
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        # Resolve field paths
        path_mapping = self._get_full_path_mapping(form)
        resolved_field = self._resolve_field(field, path_mapping)
        filter_field = self._resolve_field(filter_field, path_mapping)

        # Data Validation: Verify the field exists and is numeric in schema
        is_numeric = False
        field_label = field
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            for q in survey:
                q_name = q.get("name")
                # Check both short name and resolved path
                if q_name == field or path_mapping.get(q_name) == resolved_field or q_name == resolved_field:
                    if q.get("type") in ["integer", "decimal"]:
                        is_numeric = True
                        field_label = q.get("label", [field])[0] if isinstance(q.get("label"), list) else q.get("label", field)
                    break
        
        if not is_numeric:
             raise HTTPException(status_code=400, detail=f"Field '{field}' is not numeric or not found in schema")

        # Get total responses before filtering by numeric validity
        base_query = self.db.query(func.count(Submission.id))
        base_query, _ = self._apply_filters(
            base_query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )
        total_in_filter = base_query.scalar() or 0

        # Extract numeric values
        field_attr = self._get_json_field(resolved_field)
        query = self.db.query(field_attr)
        query, _ = self._apply_filters(
            query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )
        
        # Filter out nulls and empty strings
        query = query.filter(field_attr.isnot(None), field_attr != "")
        
        results = query.all()
        
        # Process values in Python for robust statistics
        valid_values = []
        for r in results:
            val = r[0]
            try:
                # Convert to float
                f_val = float(val)
                # Exclude negative values unless allowed
                if f_val < 0 and not allow_negative:
                    continue
                valid_values.append(f_val)
            except (ValueError, TypeError):
                continue

        valid_count = len(valid_values)
        excluded_count = total_in_filter - valid_count

        if not valid_values:
            return NumericSummaryResponse(
                field=field,
                valid_count=0,
                excluded_count=excluded_count,
                statistics=NumericStatistics(
                    mean=0.0, median=0.0, min=0.0, max=0.0
                )
            )

        # Calculate statistics using Pandas
        s = pd.Series(valid_values)
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        
        stats = NumericStatistics(
            mean=round(float(s.mean()), 2),
            median=round(float(s.median()), 2),
            min=float(s.min()),
            max=float(s.max()),
            std_dev=round(float(s.std()), 2) if len(s) > 1 else 0.0,
            q1=round(q1, 2),
            q3=round(q3, 2),
            iqr=round(q3 - q1, 2)
        )

        return NumericSummaryResponse(
            field=field,
            valid_count=valid_count,
            excluded_count=excluded_count,
            statistics=stats
        )

    def get_numeric_distribution(
        self,
        form_id: str,
        field: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
        allow_negative: bool = False,
        remove_outliers: bool = False
    ) -> NumericDistributionResponse:
        """
        Calculate detailed numeric distribution analysis including quartiles, IQR, mean, std dev, and outliers.
        """
        # 0. Find internal form ID first to resolve paths
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        # Resolve field paths
        path_mapping = self._get_full_path_mapping(form)
        resolved_field = self._resolve_field(field, path_mapping)
        filter_field = self._resolve_field(filter_field, path_mapping)

        # Data Validation: Verify the field exists and is numeric in schema
        is_numeric = False
        field_label = field
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            for q in survey:
                q_name = q.get("name")
                # Check both short name and resolved path
                if q_name == field or path_mapping.get(q_name) == resolved_field or q_name == resolved_field:
                    if q.get("type") in ["integer", "decimal"]:
                        is_numeric = True
                        field_label = q.get("label", [field])[0] if isinstance(q.get("label"), list) else q.get("label", field)
                    break
        
        if not is_numeric:
            raise HTTPException(status_code=400, detail=f"Field '{field}' is not numeric")

        # Get total responses before filtering by numeric validity
        base_query = self.db.query(func.count(Submission.id))
        base_query, _ = self._apply_filters(
            base_query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )
        total_in_filter = base_query.scalar() or 0

        # Extract numeric values
        field_attr = self._get_json_field(resolved_field)
        query = self.db.query(field_attr)
        query, _ = self._apply_filters(
            query, form_id, date_from, date_to, location, enumerator, filter_field, filter_value
        )
        
        # Filter out nulls and empty strings
        query = query.filter(field_attr.isnot(None), field_attr != "")
        
        results = query.all()
        
        # Process values in Python for robust statistics
        valid_values = []
        excluded_records = []
        
        for r in results:
            val = r[0]
            try:
                # Convert to float
                f_val = float(val)
                # Exclude negative values unless allowed
                if f_val < 0 and not allow_negative:
                    excluded_records.append(f_val)
                    continue
                valid_values.append(f_val)
            except (ValueError, TypeError):
                excluded_records.append(val)
                continue

        valid_count = len(valid_values)
        excluded_count = total_in_filter - valid_count

        # Handle empty case
        if not valid_values:
            return NumericDistributionResponse(
                field=field,
                valid_count=0,
                excluded_count=excluded_count,
                distribution=None,
                statistics=None,
                outliers=None,
                message="No valid numeric values available"
            )

        # Calculate statistics using Pandas
        s = pd.Series(valid_values)
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        
        # Calculate outliers using IQR method
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = [val for val in valid_values if val < lower_bound or val > upper_bound]
        
        # Remove outliers if requested
        if remove_outliers and outliers:
            clean_values = [val for val in valid_values if lower_bound <= val <= upper_bound]
            if clean_values:
                s = pd.Series(clean_values)
                q1 = float(s.quantile(0.25))
                q3 = float(s.quantile(0.75))
                iqr = q3 - q1
        
        distribution = Distribution(
            min=round(float(s.min()), 2),
            q1=round(q1, 2),
            median=round(float(s.median()), 2),
            q3=round(q3, 2),
            max=round(float(s.max()), 2),
            iqr=round(iqr, 2)
        )
        
        statistics = {
            "mean": round(float(s.mean()), 2),
            "std_dev": round(float(s.std()), 2) if len(s) > 1 else 0.0
        }
        
        # Log excluded records
        if excluded_records:
            logger.info(f"Numeric distribution for {field}: {len(excluded_records)} records excluded")
        
        return NumericDistributionResponse(
            field=field,
            valid_count=valid_count,
            excluded_count=excluded_count,
            distribution=distribution,
            statistics=statistics,
            outliers=sorted([round(float(o), 2) for o in outliers]) if outliers else None
        )

    def get_ordinal_fields(self, form_id: str) -> OrdinalFieldsResponse:
        """List ordinal fields with options from form schema."""
        # Find internal form ID first to resolve paths
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        path_mapping = self._get_full_path_mapping(form)
        ordinal_fields = []

        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            choices = form.form_schema["content"].get("choices", [])
            
            # Map choice lists
            choice_map = {}
            for c in choices:
                list_name = c.get("list_name")
                if list_name not in choice_map:
                    choice_map[list_name] = []
                
                label = c.get("label", [c.get("name")])[0] if isinstance(c.get("label"), list) else c.get("label", c.get("name"))
                choice_map[list_name].append(OrdinalFieldOption(
                    label=str(label),
                    value=str(c.get("name"))
                ))

            for q in survey:
                q_type = q.get("type", "")
                if q_type == "select_one":
                    select_from_list_name = q.get("select_from_list_name")
                    if select_from_list_name and select_from_list_name in choice_map:
                        options = choice_map[select_from_list_name]
                        
                        short_name = q.get("name")
                        full_path = path_mapping.get(short_name, short_name)
                        label = q.get("label", [short_name])[0] if isinstance(q.get("label"), list) else q.get("label", short_name)
                        
                        ordinal_fields.append(OrdinalFieldInfo(
                            name=full_path,
                            label=str(label),
                            options=options
                        ))

        return OrdinalFieldsResponse(form_id=str(form.id), fields=ordinal_fields)

    def _get_ordinal_category(self, label: str) -> str:
        """Heuristic to categorize Likert options."""
        label_lower = label.lower()
        
        positive_keywords = ["agree", "good", "often", "always", "excellent", "satisfied", "yes", "high", "positive", "very", "frequently"]
        negative_keywords = ["disagree", "poor", "never", "rarely", "bad", "dissatisfied", "no", "low", "negative", "seldom", "hardly"]
        neutral_keywords = ["neutral", "average", "sometimes", "neither", "maybe", "occasional", "don't know", "dnk"]
        
        # Check for strong positive/negative first
        if any(kw in label_lower for kw in ["strongly agree", "very satisfied", "very good", "excellent"]):
             return "positive"
        if any(kw in label_lower for kw in ["strongly disagree", "very dissatisfied", "very poor", "terrible"]):
             return "negative"

        if any(kw in label_lower for kw in negative_keywords):
            return "negative"
        if any(kw in label_lower for kw in positive_keywords):
            return "positive"
        if any(kw in label_lower for kw in neutral_keywords):
            return "neutral"
            
        return "neutral"

    def get_ordinal_scale_analysis(
        self,
        form_id: str,
        field: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None,
        include_null: bool = False,
        decimal_places: int = 1,
        response_type: Optional[str] = None
    ) -> OrdinalScaleAnalysisResponse:
        """Analyze ordinal/Likert scale responses with order preservation."""
        # Find form
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        path_mapping = self._get_full_path_mapping(form)
        resolved_field = self._resolve_field(field, path_mapping)
        
        # Get field definition and options order
        question_text = field
        options_order = []
        option_metadata = {} # value -> {label, order, category}
        label_to_value = {} # To handle cases where DB stores labels instead of values
        
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            choices = form.form_schema["content"].get("choices", [])
            
            target_q = None
            for q in survey:
                if q.get("name") == field or path_mapping.get(q.get("name")) == resolved_field or q.get("name") == resolved_field:
                    target_q = q
                    break
            
            if target_q:
                question_text = target_q.get("label", [field])[0] if isinstance(target_q.get("label"), list) else target_q.get("label", field)
                list_name = target_q.get("select_from_list_name")
                if list_name:
                    order = 1
                    for c in choices:
                        if c.get("list_name") == list_name:
                            val = str(c.get("name"))
                            lbl = c.get("label", [val])[0] if isinstance(c.get("label"), list) else c.get("label", val)
                            lbl = str(lbl)
                            options_order.append(val)
                            option_metadata[val] = {
                                "label": lbl,
                                "order": order,
                                "category": self._get_ordinal_category(lbl)
                            }
                            label_to_value[lbl] = val
                            order += 1

        # Retrieve data
        field_attr = self._get_json_field(resolved_field)
        query = self.db.query(field_attr)
        query, _ = self._apply_filters(query, form_id, date_from, date_to, location, enumerator)
        
        total_responses = query.count()
        if not include_null:
            query = query.filter(field_attr.isnot(None), field_attr != "")
        
        results = query.all()
        counts = {}
        for r in results:
            raw_val = str(r[0]) if r[0] is not None else "null"
            # Map label to value if necessary
            val = label_to_value.get(raw_val, raw_val)
            counts[val] = counts.get(val, 0) + 1
        
        valid_responses_count = sum(counts.get(opt, 0) for opt in options_order)
        excluded_count = total_responses - valid_responses_count
        
        responses = []
        pos_count = 0
        neg_count = 0
        neu_count = 0
        weighted_sum = 0
        
        for opt_val in options_order:
            meta = option_metadata[opt_val]
            count = counts.get(opt_val, 0)
            percentage = round((count / valid_responses_count * 100), decimal_places) if valid_responses_count > 0 else 0.0
            
            responses.append(OrdinalResponseItem(
                option=meta["label"],
                count=count,
                percentage=percentage,
                order=meta["order"],
                category=meta["category"]
            ))
            
            if meta["category"] == "positive": pos_count += count
            elif meta["category"] == "negative": neg_count += count
            else: neu_count += count
            
            weighted_sum += count * meta["order"]

        # Stats
        pos_pct = round((pos_count / valid_responses_count * 100), decimal_places) if valid_responses_count > 0 else 0.0
        neg_pct = round((neg_count / valid_responses_count * 100), decimal_places) if valid_responses_count > 0 else 0.0
        neu_pct = round((neu_count / valid_responses_count * 100), decimal_places) if valid_responses_count > 0 else 0.0
        net_score = round(pos_pct - neg_pct, decimal_places)
        mean_score = round(weighted_sum / valid_responses_count, 2) if valid_responses_count > 0 else 0.0
        
        mode = "N/A"
        if responses:
            # Avoid using max on empty sequence
            if valid_responses_count > 0:
                mode_item = max(responses, key=lambda x: x.count)
                if mode_item.count > 0:
                    mode = mode_item.option

        # Filter by response_type if requested
        if response_type and response_type != "all":
            responses = [r for r in responses if r.category == response_type]

        analysis = OrdinalAnalysisSummary(
            positive_percentage=pos_pct,
            negative_percentage=neg_pct,
            neutral_percentage=neu_pct,
            net_score=net_score,
            mean_score=mean_score,
            mode=mode,
            consistency_index=0.85 
        )
        
        metadata = OrdinalAnalysisMetadata(
            form_name=form.title,
            question_text=str(question_text),
            options_order=[option_metadata[opt]["label"] for opt in options_order],
            generated_at=datetime.utcnow(),
            filters_applied={
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
                "location": location,
                "enumerator": enumerator
            }
        )

        return OrdinalScaleAnalysisResponse(
            field=field,
            total_responses=total_responses,
            excluded_count=excluded_count,
            valid_responses=valid_responses_count,
            responses=responses,
            analysis=analysis,
            metadata=metadata,
            message="No valid responses available for the selected filters" if valid_responses_count == 0 else None
        )

    def get_ordinal_batch_analysis(self, request: OrdinalBatchAnalysisRequest) -> OrdinalBatchAnalysisResponse:
        """Analyze multiple ordinal fields simultaneously."""
        results = {}
        for field in request.fields:
            try:
                results[field] = self.get_ordinal_scale_analysis(
                    form_id=request.form_id,
                    field=field,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    location=request.location,
                    enumerator=request.enumerator,
                    include_null=request.include_null,
                    decimal_places=request.decimal_places
                )
            except Exception as e:
                logger.error(f"Error in batch analysis for field {field}: {str(e)}")
        
        return OrdinalBatchAnalysisResponse(form_id=request.form_id, results=results)

    def get_ordinal_trends(
        self,
        form_id: str,
        field: str,
        granularity: str = "month",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None
    ) -> OrdinalTrendsResponse:
        """Analyze trends of ordinal scores over time."""
        # Find form
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        path_mapping = self._get_full_path_mapping(form)
        resolved_field = self._resolve_field(field, path_mapping)
        
        # Get option categories
        option_categories = {}
        label_to_value = {}
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            choices = form.form_schema["content"].get("choices", [])
            target_q = next((q for q in survey if q.get("name") == field or path_mapping.get(q.get("name")) == resolved_field or q.get("name") == resolved_field), None)
            if target_q:
                list_name = target_q.get("select_from_list_name")
                if list_name:
                    for c in choices:
                        if c.get("list_name") == list_name:
                            val = str(c.get("name"))
                            lbl = c.get("label", [val])[0] if isinstance(c.get("label"), list) else c.get("label", val)
                            lbl = str(lbl)
                            option_categories[val] = self._get_ordinal_category(lbl)
                            label_to_value[lbl] = val

        # Retrieve data with dates
        field_attr = self._get_json_field(resolved_field)
        query = self.db.query(field_attr, Submission.created_at)
        query, _ = self._apply_filters(query, form_id, date_from, date_to, location)
        query = query.filter(field_attr.isnot(None), field_attr != "")
        
        results = query.all()
        if not results:
            return OrdinalTrendsResponse(field=field, granularity=granularity, trends=[])

        # Process results with label-to-value mapping
        processed_results = []
        for val, date in results:
            processed_results.append({
                "value": label_to_value.get(str(val), str(val)),
                "date": date
            })

        df = pd.DataFrame(processed_results)
        df["date"] = pd.to_datetime(df["date"])
        
        if granularity == "day":
            df["period"] = df["date"].dt.strftime("%Y-%m-%d")
        elif granularity == "week":
            df["period"] = df["date"].dt.strftime("%Y-W%U")
        elif granularity == "year":
            df["period"] = df["date"].dt.strftime("%Y")
        else: # month
            df["period"] = df["date"].dt.strftime("%Y-%m")

        trends = []
        for period, group in df.groupby("period"):
            p_counts = group["value"].value_counts().to_dict()
            total = len(group)
            
            pos = sum(p_counts.get(val, 0) for val, cat in option_categories.items() if cat == "positive")
            neg = sum(p_counts.get(val, 0) for val, cat in option_categories.items() if cat == "negative")
            neu = sum(p_counts.get(val, 0) for val, cat in option_categories.items() if cat == "neutral")
            
            pos_pct = round((pos / total * 100), 1)
            neg_pct = round((neg / total * 100), 1)
            neu_pct = round((neu / total * 100), 1)
            
            trends.append(OrdinalTrendItem(
                period=str(period),
                positive_percentage=pos_pct,
                negative_percentage=neg_pct,
                neutral_percentage=neu_pct,
                net_score=round(pos_pct - neg_pct, 1),
                count=total
            ))

        return OrdinalTrendsResponse(field=field, granularity=granularity, trends=sorted(trends, key=lambda x: x.period))

    def _detect_field_type(self, form: FormModel, field: str, path_mapping: Dict[str, str]) -> str:
        """Detect field type from form schema."""
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            resolved_field = self._resolve_field(field, path_mapping)
            target_q = next((q for q in survey if q.get("name") == field or path_mapping.get(q.get("name")) == resolved_field or q.get("name") == resolved_field), None)
            if target_q:
                return target_q.get("type", "unknown")
        return "unknown"

    def get_multiselect_analysis(
        self,
        form_id: str,
        field: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None
    ):
        """Analyze any field type (ordinal, multi-select, etc.) with auto-detection."""
        # Find form
        form_filter = or_(FormModel.kobo_form_id == form_id)
        if form_id.isdigit():
            form_filter = or_(FormModel.kobo_form_id == form_id, FormModel.id == int(form_id))
        form = self.db.query(FormModel).filter(form_filter).first()
        if not form:
            raise HTTPException(status_code=404, detail=f"Form {form_id} not found")

        path_mapping = self._get_full_path_mapping(form)
        
        # Auto-detect field type
        field_type = self._detect_field_type(form, field, path_mapping)
        
        # Route to appropriate analysis method
        if field_type == "select_multiple":
            return self._analyze_multiselect_field(form, field, form_id, date_from, date_to, location, enumerator)
        else:
            # For ordinal/select_one and other types, use ordinal analysis
            return self.get_ordinal_scale_analysis(
                form_id=form_id,
                field=field,
                date_from=date_from,
                date_to=date_to,
                location=location,
                enumerator=enumerator,
                include_null=False,
                decimal_places=1
            )

    def _analyze_multiselect_field(
        self,
        form: FormModel,
        field: str,
        form_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location: Optional[str] = None,
        enumerator: Optional[str] = None
    ) -> MultiSelectAnalysisResponse:
        """Analyze select_multiple field type."""
        path_mapping = self._get_full_path_mapping(form)
        resolved_field = self._resolve_field(field, path_mapping)
        
        # Get field definition and options
        question_text = field
        options_list = []
        option_metadata = {}
        label_to_value = {}
        
        if form.form_schema and "content" in form.form_schema:
            survey = form.form_schema["content"].get("survey", [])
            choices = form.form_schema["content"].get("choices", [])
            
            target_q = next((q for q in survey if q.get("name") == field or path_mapping.get(q.get("name")) == resolved_field or q.get("name") == resolved_field), None)
            
            if target_q:
                question_text = target_q.get("label", [field])[0] if isinstance(target_q.get("label"), list) else target_q.get("label", field)
                list_name = target_q.get("select_from_list_name")
                if list_name:
                    for c in choices:
                        if c.get("list_name") == list_name:
                            val = str(c.get("name"))
                            lbl = c.get("label", [val])[0] if isinstance(c.get("label"), list) else c.get("label", val)
                            lbl = str(lbl)
                            options_list.append(val)
                            option_metadata[val] = {"label": lbl}
                            label_to_value[lbl] = val

        # Retrieve data
        field_attr = self._get_json_field(resolved_field)
        query = self.db.query(field_attr)
        query, _ = self._apply_filters(query, form_id, date_from, date_to, location, enumerator)
        
        total_respondents = query.count()
        query = query.filter(field_attr.isnot(None), field_attr != "")
        results = query.all()
        
        # Count responses with data
        respondents_with_data = len(results)
        excluded_count = total_respondents - respondents_with_data
        
        # Parse multi-select responses (space or space-separated for KoBo)
        option_counts = {opt: 0 for opt in options_list}
        total_selections = 0
        
        for r in results:
            raw_val = str(r[0]) if r[0] is not None else ""
            if not raw_val:
                continue
            
            # KoBo stores select_multiple as space-separated values
            selected_vals = raw_val.split()
            for sel_val in selected_vals:
                sel_val = sel_val.strip()
                # Try to map label to value if needed
                mapped_val = label_to_value.get(sel_val, sel_val)
                if mapped_val in option_counts:
                    option_counts[mapped_val] += 1
                    total_selections += 1
        
        # Build response
        options = []
        for opt_val in options_list:
            count = option_counts[opt_val]
            # Percentage of total selections
            selection_percentage = round((count / total_selections * 100), 1) if total_selections > 0 else 0.0
            # Percentage of total respondents (this can exceed 100%)
            respondent_percentage = round((count / total_respondents * 100), 1) if total_respondents > 0 else 0.0
            
            options.append(MultiSelectOption(
                option=option_metadata[opt_val]["label"],
                count=count,
                percentage=selection_percentage,
                respondent_percentage=respondent_percentage
            ))
        
        # Sort by count descending
        options.sort(key=lambda x: x.count, reverse=True)
        
        metadata = {
            "form_name": form.title,
            "question_text": str(question_text),
            "generated_at": datetime.utcnow().isoformat(),
            "filters_applied": {
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
                "location": location,
                "enumerator": enumerator
            }
        }
        
        return MultiSelectAnalysisResponse(
            field=field,
            total_respondents=total_respondents,
            respondents_with_data=respondents_with_data,
            excluded_count=excluded_count,
            total_selections=total_selections,
            options=options,
            metadata=metadata,
            message="No respondents with data" if respondents_with_data == 0 else None
        )

    def get_multiselect_batch_analysis(self, request: MultiSelectBatchRequest) -> MultiSelectBatchResponse:
        """Analyze multiple fields of any type simultaneously (ordinal, multi-select, etc.)."""
        results = {}
        for field in request.fields:
            try:
                results[field] = self.get_multiselect_analysis(
                    form_id=request.form_id,
                    field=field,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    location=request.location if hasattr(request, 'location') else None,
                    enumerator=request.enumerator if hasattr(request, 'enumerator') else None
                )
            except Exception as e:
                logger.error(f"Error in batch analysis for field {field}: {str(e)}")
        
        return MultiSelectBatchResponse(form_id=request.form_id, results=results)
