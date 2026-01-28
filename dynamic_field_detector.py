"""Dynamic field detection for forms - auto-detects gender and province/district fields."""

import json
from typing import Optional, Dict, List, Tuple
from models import Form as FormModel, Submission
from sqlalchemy.orm import Session


def detect_province_district_fields_for_form(
    form: FormModel,
    raw_submission_samples: Optional[List[dict]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Auto-detect province and district field names for a form from its schema and,
    if needed, from raw submission keys. Each form can use different column names
    (e.g. wilayat, info/province, location/province_name). Returns (province_field, district_field)
    as schema-style paths (e.g. "info/province"). Used during ETL sync so province/district
    are correctly filled per form.
    """
    province_keywords = [
        "province", "wilayat", "state", "region", "admin1", "adm1",
        "governorate", "ولایت", "صوبہ", "province_name", "name_province",
    ]
    district_keywords = [
        "district", "woleswali", "wuluswali", "wuleswali", "county", "admin2", "adm2",
        "municipality", "ولسوالی", "ضلع", "district_name", "name_district",
    ]

    schema = _parse_schema(form.form_schema) if form else None
    survey = (schema or {}).get("content", {}).get("survey", [])

    province_field: Optional[str] = None
    district_field: Optional[str] = None

    # 1) Prefer form schema: match by field 'name' or 'label'
    for field in survey:
        name = field.get("name") or ""
        label = field.get("label")
        if isinstance(label, list):
            label = label[0] if label else ""
        label = (label or "").strip()
        name_lower = name.lower()
        label_lower = label.lower()
        name_last = name_lower.split("/")[-1] if name else ""

        if not province_field:
            if any(k in name_lower or k in label_lower or k in name_last for k in province_keywords):
                if "district" not in name_lower and "district" not in label_lower:
                    province_field = name

        if not district_field:
            if any(k in name_lower or k in label_lower or k in name_last for k in district_keywords):
                if "province" not in name_lower and "province" not in label_lower:
                    district_field = name

    # 2) Fallback: scan keys in raw submission data (paths like info/province)
    if (province_field is None or district_field is None) and raw_submission_samples:
        all_paths: set[str] = set()
        for raw in raw_submission_samples:
            if not isinstance(raw, dict):
                continue
            body = raw.get("body")
            effective = {**(body or {}), **raw} if isinstance(body, dict) else raw
            all_paths |= _get_leaf_paths_from_dict(effective)

        for p in sorted(all_paths):
            pl = p.lower()
            last = p.split("/")[-1].lower() if "/" in p else pl
            if province_field is None and any(k in pl or k in last for k in province_keywords):
                if "district" not in pl:
                    province_field = p
            if district_field is None and any(k in pl or k in last for k in district_keywords):
                if "province" not in pl:
                    district_field = p

    return (province_field, district_field)


def _get_leaf_paths_from_dict(d: dict, prefix: str = "") -> set[str]:
    """Recursively collect leaf paths (e.g. info/province) from nested dict. Skips keys starting with '_'."""
    out: set[str] = set()
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        if k.startswith("_") and k.lower() not in ("_province", "_district"):
            continue
        p = f"{prefix}/{k}" if prefix else k
        if isinstance(v, dict):
            # Skip geopoint-like objects
            keys = set(v.keys())
            if keys <= {"lat", "latitude", "lon", "lng", "longitude", "alt", "accuracy"} and any(
                x in keys for x in ("lat", "latitude")
            ) and any(x in keys for x in ("lon", "lng", "longitude")):
                out.add(p)
            else:
                out |= _get_leaf_paths_from_dict(v, p)
        else:
            out.add(p)
    return out


def detect_province_field(form: FormModel, submissions: List[Submission]) -> Optional[str]:
    """
    Auto-detect province/location field from form schema and submission data.
    Prioritizes 'province' and 'district' over generic 'location'.
    """
    if not submissions:
        return None
    
    schema = _parse_schema(form.form_schema)
    field_labels = _extract_field_labels(schema) if schema else {}
    
    all_submission_fields = _get_all_submission_fields(submissions)
    
    priority_fields_order = [
        ('province', 0),
        ('region', 1),
        ('state', 1),
        ('admin1', 1),
        ('area', 1),
        ('division', 1),
        ('district', 2),
    ]
    generic_location = ['location', 'geopoint', 'gps_location', 'latitude', 'longitude']
    
    candidates = []
    
    for field_name in sorted(all_submission_fields):
        if field_name.startswith('_'):
            continue
            
        short_name = field_name.split('/')[-1].lower()
        label = field_labels.get(field_name.split('/')[-1], field_name)
        label_lower = label.lower() if label else ""
        
        if not _has_data(submissions, field_name):
            continue
        
        best_priority = None
        for keyword, priority in priority_fields_order:
            if keyword in short_name or keyword in label_lower:
                best_priority = priority
                break
        
        if best_priority is not None:
            candidates.append((best_priority, field_name))
        else:
            for g in generic_location:
                if g in short_name or g in label_lower:
                    candidates.append((100, field_name))
                    break
    
    if candidates:
        candidates.sort()
        return candidates[0][1]
    
    return None


def detect_gender_field(form: FormModel, submissions: List[Submission]) -> Optional[str]:
    """
    Auto-detect gender/sex field from form schema and submission data.
    Searches for field labels containing keywords and validates cardinality.
    """
    gender_keywords = ['gender', 'sex', 'male', 'female', 'respondent_gender', 'sex_of_household']
    
    if not submissions:
        return None
    
    schema = _parse_schema(form.form_schema)
    field_labels = _extract_field_labels(schema) if schema else {}
    
    all_submission_fields = _get_all_submission_fields(submissions)
    
    for field_name in sorted(all_submission_fields):
        if not field_name.startswith('_'):
            short_name = field_name.split('/')[-1]
            label = field_labels.get(short_name, field_name)
            label_lower = label.lower() if label else ""
            if any(keyword in label_lower for keyword in gender_keywords):
                if _has_data(submissions, field_name):
                    unique_vals = _count_unique_values(submissions, field_name)
                    if 2 <= unique_vals <= 4:
                        return field_name
    
    return None


def _get_all_submission_fields(submissions: List[Submission]) -> set:
    """Get all unique field names from submission data."""
    all_fields = set()
    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data or {}
        if isinstance(payload, dict):
            all_fields.update(payload.keys())
    return all_fields


def _parse_schema(schema) -> Optional[Dict]:
    """Parse form schema (handle JSON string or dict)."""
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, str):
        try:
            return json.loads(schema)
        except:
            return None
    return None


def _extract_field_labels(schema: Dict) -> Dict[str, str]:
    """Extract field names and their labels from form schema."""
    field_labels = {}
    
    try:
        content = schema.get('content', {})
        survey = content.get('survey', [])
        
        for field in survey:
            name = field.get('name')
            label = field.get('label', '')
            
            if name:
                if isinstance(label, list) and len(label) > 0:
                    label = label[0]
                field_labels[name] = str(label)
    except:
        pass
    
    return field_labels


def _has_data(submissions: List[Submission], field_name: str) -> bool:
    """Check if field has non-empty values in submissions."""
    count = 0
    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data or {}
        if isinstance(payload, dict) and payload.get(field_name) not in (None, ''):
            count += 1
    return count > 0


def _count_unique_values(submissions: List[Submission], field_name: str) -> int:
    """Count unique values for a field."""
    unique_vals = set()
    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data or {}
        if isinstance(payload, dict):
            val = payload.get(field_name)
            if val not in (None, ''):
                unique_vals.add(str(val).lower().strip())
    return len(unique_vals)


def get_field_data(submissions: List[Submission], field_name: Optional[str]) -> dict:
    """
    Get unique values for a field with their counts.
    Returns: {value: count}
    """
    if not field_name:
        return {}
    
    counts = {}
    for sub in submissions:
        payload = sub.cleaned_data or sub.submission_data or {}
        if isinstance(payload, dict):
            val = payload.get(field_name)
            if val not in (None, ''):
                val_str = str(val).lower().strip()
                counts[val_str] = counts.get(val_str, 0) + 1
    
    return counts
