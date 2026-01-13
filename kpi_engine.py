"""KPI Engine for computing Key Performance Indicators."""
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session

from models import KPIDefinition, KPIValue, Submission
from report_filters import FilterContext, get_nested_field_value

logger = logging.getLogger(__name__)


@dataclass
class KPIComputationResult:
    """Result of a single KPI computation."""
    
    kpi_code: str
    label: str
    unit: str
    category: str
    sub_category: Optional[str]
    
    value: float
    baseline: Optional[float]
    target: Optional[float]
    
    sample_size: int
    valid_sample_size: int
    
    trend: Optional[str] = None  # up, down, stable, no_data
    
    def progress_to_target_pct(self) -> Optional[float]:
        """Calculate progress towards target (as percentage)."""
        if self.baseline is None or self.target is None:
            return None
        
        total_gap = self.target - self.baseline
        if total_gap == 0:
            return 0.0
        
        current_gap = self.value - self.baseline
        progress = (current_gap / total_gap) * 100.0
        
        return max(0.0, min(100.0, progress))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for response."""
        return {
            "kpi_code": self.kpi_code,
            "kpi_label": self.label,
            "value": round(self.value, 2),
            "unit": self.unit,
            "baseline": self.baseline,
            "target": self.target,
            "progress_to_target_pct": self.progress_to_target_pct(),
            "sample_size": self.sample_size,
            "valid_sample_size": self.valid_sample_size,
            "trend": self.trend,
            "category": self.category,
            "sub_category": self.sub_category,
        }


class KPIEngine:
    """
    Compute KPIs from submissions using registered KPI definitions.
    Handles computation logic, time-series aggregation, and caching.
    """
    
    def __init__(self, db: Session):
        """Initialize KPI engine with database session."""
        self.db = db
        self._kpi_cache: Dict[str, KPIDefinition] = {}
        self._load_kpi_definitions()
    
    def _load_kpi_definitions(self):
        """Load all active KPI definitions from database."""
        definitions = self.db.query(KPIDefinition).filter(KPIDefinition.is_active == True).all()
        for defn in definitions:
            self._kpi_cache[defn.kpi_code] = defn
        logger.info(f"Loaded {len(self._kpi_cache)} KPI definitions")
    
    def register_kpi(self, kpi_def: KPIDefinition) -> None:
        """Register a KPI definition."""
        self._kpi_cache[kpi_def.kpi_code] = kpi_def
        logger.debug(f"Registered KPI: {kpi_def.kpi_code}")
    
    def get_kpi_definition(self, kpi_code: str) -> Optional[KPIDefinition]:
        """Get KPI definition by code."""
        return self._kpi_cache.get(kpi_code)
    
    def list_kpis(
        self,
        category: Optional[str] = None,
        include_custom: bool = True
    ) -> List[KPIDefinition]:
        """List all registered KPI definitions."""
        kpis = list(self._kpi_cache.values())
        
        if category:
            kpis = [kpi for kpi in kpis if kpi.report_category == category]
        
        if not include_custom:
            kpis = [kpi for kpi in kpis if not kpi.is_custom]
        
        return kpis
    
    def compute(
        self,
        kpi_code: str,
        submissions: List[Submission],
        context: Optional[FilterContext] = None
    ) -> Optional[KPIComputationResult]:
        """
        Compute a single KPI for given submissions.
        
        Args:
            kpi_code: KPI identifier
            submissions: List of submissions to analyze
            context: Optional filter context
        
        Returns:
            KPIComputationResult or None if KPI not found
        """
        kpi_def = self.get_kpi_definition(kpi_code)
        if not kpi_def:
            logger.warning(f"KPI not found: {kpi_code}")
            return None
        
        computation_logic = kpi_def.computation_logic or {}
        
        try:
            value = self._evaluate_computation(submissions, computation_logic)
        except Exception as e:
            logger.error(f"Error computing KPI {kpi_code}: {e}")
            value = 0.0
        
        valid_sample_size = len([s for s in submissions if not s.cleaned_data or not s.cleaned_data.get("_has_errors")])
        
        result = KPIComputationResult(
            kpi_code=kpi_def.kpi_code,
            label=kpi_def.label,
            unit=kpi_def.unit,
            category=kpi_def.report_category,
            sub_category=kpi_def.sub_category,
            value=value,
            baseline=kpi_def.baseline_value,
            target=kpi_def.target_value,
            sample_size=len(submissions),
            valid_sample_size=valid_sample_size,
            trend=self._calculate_trend(kpi_code, submissions),
        )
        
        return result
    
    def compute_all(
        self,
        submissions: List[Submission],
        context: Optional[FilterContext] = None,
        category: Optional[str] = None
    ) -> List[KPIComputationResult]:
        """
        Compute all registered KPIs for given submissions.
        
        Args:
            submissions: List of submissions
            context: Optional filter context
            category: Filter by KPI category
        
        Returns:
            List of KPIComputationResult objects
        """
        results = []
        kpis = self.list_kpis(category=category)
        
        for kpi_def in kpis:
            result = self.compute(kpi_def.kpi_code, submissions, context)
            if result:
                results.append(result)
        
        return results
    
    def compute_time_series(
        self,
        kpi_code: str,
        submissions: List[Submission],
        granularity: str = "monthly"
    ) -> List[Dict[str, Any]]:
        """
        Compute KPI over time with specified granularity.
        
        Args:
            kpi_code: KPI identifier
            submissions: List of submissions
            granularity: 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
        
        Returns:
            List of {period, period_label, value, sample_size, baseline, target}
        """
        if not submissions:
            return []
        
        dates = [s.created_at for s in submissions if s.created_at]
        if not dates:
            return []
        
        min_date = min(dates)
        max_date = max(dates)
        
        periods = self._generate_periods(min_date, max_date, granularity)
        results = []
        
        kpi_def = self.get_kpi_definition(kpi_code)
        if not kpi_def:
            return []
        
        for period_start, period_end, period_label in periods:
            period_submissions = [
                s for s in submissions
                if s.created_at and period_start <= s.created_at < period_end
            ]
            
            if not period_submissions:
                results.append({
                    "period": period_start.strftime("%Y-%m-%d"),
                    "period_label": period_label,
                    "value": None,
                    "sample_size": 0,
                    "baseline": kpi_def.baseline_value,
                    "target": kpi_def.target_value,
                })
                continue
            
            result = self.compute(kpi_code, period_submissions)
            if result:
                results.append({
                    "period": period_start.strftime("%Y-%m-%d"),
                    "period_label": period_label,
                    "value": result.value,
                    "sample_size": result.sample_size,
                    "baseline": result.baseline,
                    "target": result.target,
                })
        
        return results
    
    def compute_by_dimension(
        self,
        kpi_code: str,
        submissions: List[Submission],
        dimension_field: str
    ) -> Dict[str, KPIComputationResult]:
        """
        Compute KPI broken down by a field dimension.
        
        Args:
            kpi_code: KPI identifier
            submissions: List of submissions
            dimension_field: Field to group by (e.g., 'info/province')
        
        Returns:
            {dimension_value: KPIComputationResult}
        """
        grouped = {}
        
        for sub in submissions:
            payload = sub.cleaned_data or sub.submission_data or {}
            dim_value = get_nested_field_value(payload, dimension_field)
            
            if dim_value is None or dim_value == "":
                dim_value = "<undefined>"
            
            dim_value_str = str(dim_value)
            if dim_value_str not in grouped:
                grouped[dim_value_str] = []
            
            grouped[dim_value_str].append(sub)
        
        results = {}
        for dim_value, subs in grouped.items():
            result = self.compute(kpi_code, subs)
            if result:
                results[dim_value] = result
        
        return results
    
    def _evaluate_computation(
        self,
        submissions: List[Submission],
        logic: Dict[str, Any]
    ) -> float:
        """
        Evaluate KPI computation logic against submissions.
        
        Logic format:
        {
            "type": "percentage" | "count" | "average" | "sum",
            "numerator": {...},    # condition or field
            "denominator": {...},  # condition or "*" for all
            "field": "...",        # For average/sum
        }
        """
        if not logic:
            return 0.0
        
        computation_type = logic.get("type", "count")
        
        if computation_type == "percentage":
            numerator_condition = logic.get("numerator")
            denominator_condition = logic.get("denominator")
            
            numerator_count = self._count_matching(submissions, numerator_condition)
            denominator_count = self._count_matching(submissions, denominator_condition)
            
            if denominator_count == 0:
                return 0.0
            
            return (numerator_count / denominator_count) * 100.0
        
        elif computation_type == "count":
            condition = logic.get("condition")
            return float(self._count_matching(submissions, condition))
        
        elif computation_type == "average":
            field = logic.get("field")
            condition = logic.get("condition")
            
            values = self._collect_numeric_values(submissions, field, condition)
            if not values:
                return 0.0
            
            return sum(values) / len(values)
        
        elif computation_type == "sum":
            field = logic.get("field")
            condition = logic.get("condition")
            
            values = self._collect_numeric_values(submissions, field, condition)
            return sum(values) if values else 0.0
        
        return 0.0
    
    def _count_matching(
        self,
        submissions: List[Submission],
        condition: Optional[Dict[str, Any]]
    ) -> int:
        """Count submissions matching a condition."""
        if condition is None:
            return len(submissions)
        
        if condition == "*":
            return len(submissions)
        
        count = 0
        for sub in submissions:
            if self._matches_condition(sub, condition):
                count += 1
        
        return count
    
    def _collect_numeric_values(
        self,
        submissions: List[Submission],
        field: str,
        condition: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """Collect numeric values from submissions matching condition."""
        values = []
        
        for sub in submissions:
            if condition and not self._matches_condition(sub, condition):
                continue
            
            payload = sub.cleaned_data or sub.submission_data or {}
            value = get_nested_field_value(payload, field)
            
            if value is None or value == "":
                continue
            
            try:
                numeric_value = float(value)
                values.append(numeric_value)
            except (ValueError, TypeError):
                continue
        
        return values
    
    def _matches_condition(
        self,
        submission: Submission,
        condition: Dict[str, Any]
    ) -> bool:
        """Check if submission matches a condition."""
        if not condition:
            return True
        
        payload = submission.cleaned_data or submission.submission_data or {}
        
        field = condition.get("field")
        if not field:
            return True
        
        value = get_nested_field_value(payload, field)
        operator = condition.get("operator", "==")
        expected = condition.get("value")
        
        if operator == "==":
            return str(value) == str(expected)
        elif operator == "!=":
            return str(value) != str(expected)
        elif operator == "in":
            return value in (expected if isinstance(expected, list) else [expected])
        elif operator == "not_in":
            return value not in (expected if isinstance(expected, list) else [expected])
        elif operator == ">":
            try:
                return float(value) > float(expected)
            except (ValueError, TypeError):
                return False
        elif operator == "<":
            try:
                return float(value) < float(expected)
            except (ValueError, TypeError):
                return False
        elif operator == ">=":
            try:
                return float(value) >= float(expected)
            except (ValueError, TypeError):
                return False
        elif operator == "<=":
            try:
                return float(value) <= float(expected)
            except (ValueError, TypeError):
                return False
        
        return True
    
    def _calculate_trend(
        self,
        kpi_code: str,
        submissions: List[Submission],
        lookback_days: int = 30
    ) -> Optional[str]:
        """
        Calculate trend (up/down/stable) by comparing last period to previous.
        
        Returns: 'up', 'down', 'stable', or None if insufficient data
        """
        if not submissions or len(submissions) < 2:
            return None
        
        now = datetime.utcnow()
        cutoff = now - timedelta(days=lookback_days)
        
        current_period = [s for s in submissions if s.created_at and s.created_at >= cutoff]
        previous_period = [s for s in submissions if s.created_at and s.created_at < cutoff]
        
        if not current_period or not previous_period:
            return None
        
        current_result = self.compute(kpi_code, current_period)
        previous_result = self.compute(kpi_code, previous_period)
        
        if not current_result or not previous_result:
            return None
        
        change = current_result.value - previous_result.value
        
        if abs(change) < 0.5:
            return "stable"
        elif change > 0:
            return "up"
        else:
            return "down"
    
    def _generate_periods(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str
    ) -> List[Tuple[datetime, datetime, str]]:
        """Generate period boundaries based on granularity."""
        periods = []
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if granularity == "daily":
            while current <= end_date:
                period_end = current + timedelta(days=1)
                label = current.strftime("%Y-%m-%d")
                periods.append((current, period_end, label))
                current = period_end
        
        elif granularity == "weekly":
            monday = current - timedelta(days=current.weekday())
            while monday <= end_date:
                period_end = monday + timedelta(days=7)
                label = monday.strftime("Week of %Y-%m-%d")
                periods.append((monday, period_end, label))
                monday = period_end
        
        elif granularity == "monthly":
            while current.month <= end_date.month or current.year < end_date.year:
                if current.month == 12:
                    period_end = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    period_end = current.replace(month=current.month + 1, day=1)
                
                label = current.strftime("%B %Y")
                periods.append((current, period_end, label))
                current = period_end
        
        elif granularity == "quarterly":
            while current <= end_date:
                quarter = (current.month - 1) // 3 + 1
                if quarter == 4:
                    period_end = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    period_end = current.replace(month=(quarter * 3) + 1, day=1)
                
                label = f"Q{quarter} {current.year}"
                periods.append((current, period_end, label))
                current = period_end
        
        elif granularity == "annual":
            while current <= end_date:
                period_end = current.replace(year=current.year + 1, month=1, day=1)
                label = current.strftime("%Y")
                periods.append((current, period_end, label))
                current = period_end
        
        return periods
