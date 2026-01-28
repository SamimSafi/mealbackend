"""Quick test for detect_province_district_fields_for_form and ETL extract."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dynamic_field_detector import detect_province_district_fields_for_form, _get_leaf_paths_from_dict

# Test _get_leaf_paths_from_dict
d = {"info": {"province": "Balkh", "district": "Sholgara"}}
paths = _get_leaf_paths_from_dict(d)
print("paths from nested:", paths)
assert "info/province" in paths and "info/district" in paths

# Mock form with schema (wilayat / wuleswali)
class F:
    form_schema = {
        "content": {
            "survey": [
                {"name": "info/wilayat", "label": "ولایت"},
                {"name": "info/wuleswali", "label": "ولسوالی"},
            ]
        }
    }

prov, dist = detect_province_district_fields_for_form(F(), None)
print("from schema wilayat/wuleswali: province=%r district=%r" % (prov, dist))
assert prov == "info/wilayat"
assert dist == "info/wuleswali"

# Form with English names
class F2:
    form_schema = {
        "content": {
            "survey": [
                {"name": "location/province_name", "label": "Province"},
                {"name": "location/district_name", "label": "District"},
            ]
        }
    }

p2, d2 = detect_province_district_fields_for_form(F2(), None)
print("from schema province_name/district_name: province=%r district=%r" % (p2, d2))
assert p2 == "location/province_name"
assert d2 == "location/district_name"

# ETL _get_value_for_path / extract (needs DB, so we only test the ETL extract logic with a dummy)
from etl import ETLPipeline

class DummyDB:
    pass

pipe = ETLPipeline(DummyDB())
sub = {"info": {"province": "Herat", "district": "Herat City"}}
cleaned = {"info_province": "Herat", "info_district": "Herat City"}
p, d = pipe.extract_province_district_from_data(
    sub, cleaned,
    province_field="info/province",
    district_field="info/district",
)
print("ETL extract with detected info/province, info/district: province=%r district=%r" % (p, d))
assert p == "Herat" and d == "Herat City"

# Without detected fields, fallback should still work
p3, d3 = pipe.extract_province_district_from_data(sub, cleaned)
print("ETL extract fallback: province=%r district=%r" % (p3, d3))
assert p3 == "Herat" and d3 == "Herat City"

# _province / _district and xxx/province, xxx_district (fallback + scan)
sub4 = {"_province": "Balkh", "_district": "Sholgara"}
cleaned4 = {}
p4, d4 = pipe.extract_province_district_from_data(sub4, cleaned4)
print("ETL _province/_district: province=%r district=%r" % (p4, d4))
assert p4 == "Balkh" and d4 == "Sholgara"

# Scan: group/province and location_district (no configured/detected fields)
sub5 = {"group": {"province": "Kabul"}, "location_district": "District 1"}
cleaned5 = {"group_province": "Kabul", "location_district": "District 1"}
p5, d5 = pipe.extract_province_district_from_data(sub5, cleaned5)
print("ETL scan group/province, location_district: province=%r district=%r" % (p5, d5))
assert p5 == "Kabul" and d5 == "District 1"

# _get_leaf_paths includes _province, _district
d6 = {"_province": "X", "_district": "Y", "_id": 1}
paths6 = _get_leaf_paths_from_dict(d6)
print("paths with _province/_district:", paths6)
assert "_province" in paths6 and "_district" in paths6 and "_id" not in paths6

print("All tests passed.")
