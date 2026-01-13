"""
Seed script to register standard NGO/UN KPI definitions.

This script creates standard KPIs for all categories:
- WASH (Water, Sanitation, Hygiene)
- Nutrition & Health
- Child Protection
- Education
- Food Security
- Livelihoods

Run with: python scripts/seed_kpis.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import KPIDefinition


STANDARD_KPIS = [
    {
        "kpi_code": "water_access_rate",
        "label": "% Households with Access to Safe Water",
        "description": "Proportion of households with access to improved water source",
        "unit": "%",
        "formula_text": "count(water_source IN ['piped', 'borehole', 'well']) / count(*) * 100",
        "report_category": "WASH",
        "sub_category": "Water Supply",
        "indicator_type": "outcome",
        "baseline_value": 45.0,
        "target_value": 70.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "water_source", "operator": "in", "value": ["piped", "borehole", "well"]},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "sanitation_facility_rate",
        "label": "% Households with Access to Improved Sanitation",
        "description": "Proportion of households with improved sanitation facility",
        "unit": "%",
        "formula_text": "count(toilet_type IN ['flush', 'pit_latrine_ventilated']) / count(*) * 100",
        "report_category": "WASH",
        "sub_category": "Sanitation",
        "indicator_type": "outcome",
        "baseline_value": 35.0,
        "target_value": 60.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "toilet_type", "operator": "in", "value": ["flush", "pit_latrine_ventilated"]},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "hand_washing_practice",
        "label": "% Households with Hand Washing Facilities",
        "description": "Proportion of households with functional hand washing facility",
        "unit": "%",
        "formula_text": "count(handwash_facility == 'yes') / count(*) * 100",
        "report_category": "WASH",
        "sub_category": "Hygiene",
        "indicator_type": "outcome",
        "baseline_value": 25.0,
        "target_value": 50.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "handwash_facility", "operator": "==", "value": "yes"},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "child_malnutrition_rate",
        "label": "% Children with Acute Malnutrition (MUAC < 115mm)",
        "description": "Proportion of children 6-59 months with MUAC < 115mm",
        "unit": "%",
        "formula_text": "count(muac < 115) / count(age_group IN ['6-59months']) * 100",
        "report_category": "Nutrition",
        "sub_category": "Child Nutrition",
        "indicator_type": "outcome",
        "baseline_value": 28.0,
        "target_value": 15.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "muac", "operator": "<", "value": 115},
            "denominator": {"field": "age_group", "operator": "==", "value": "6-59months"}
        }
    },
    {
        "kpi_code": "stunting_rate",
        "label": "% Children with Stunting (Height-for-Age < -2SD)",
        "description": "Proportion of children 0-59 months with stunting",
        "unit": "%",
        "formula_text": "count(stunting == 'yes') / count(age_group IN ['0-59months']) * 100",
        "report_category": "Nutrition",
        "sub_category": "Child Nutrition",
        "indicator_type": "outcome",
        "baseline_value": 42.0,
        "target_value": 25.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "stunting", "operator": "==", "value": "yes"},
            "denominator": {"field": "age_group", "operator": "==", "value": "0-59months"}
        }
    },
    {
        "kpi_code": "infant_mortality_rate",
        "label": "Infant Mortality Rate (per 1000 live births)",
        "description": "Number of infants dying before age 1 per 1000 live births",
        "unit": "per 1000",
        "formula_text": "count(child_died == 'yes' AND age_at_death < 12) / count(*) * 1000",
        "report_category": "Nutrition",
        "sub_category": "Health",
        "indicator_type": "outcome",
        "baseline_value": 65.0,
        "target_value": 40.0,
        "is_custom": False,
        "computation_logic": {
            "type": "count",
            "condition": {"field": "child_died", "operator": "==", "value": "yes"}
        }
    },
    {
        "kpi_code": "child_labor_prevalence",
        "label": "% Children (5-17 years) Engaged in Child Labor",
        "description": "Proportion of children 5-17 years involved in economic or domestic labor",
        "unit": "%",
        "formula_text": "count(engaging_in_labor == 'yes') / count(age_group IN ['5-17']) * 100",
        "report_category": "Protection",
        "sub_category": "Child Labor",
        "indicator_type": "outcome",
        "baseline_value": 35.0,
        "target_value": 15.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "engaging_in_labor", "operator": "==", "value": "yes"},
            "denominator": {"field": "age_group", "operator": "==", "value": "5-17"}
        }
    },
    {
        "kpi_code": "child_marriage_rate",
        "label": "% Mothers Married Before Age 18",
        "description": "Proportion of women 15-49 married before age 18",
        "unit": "%",
        "formula_text": "count(married_before_18 == 'yes') / count(age >= 18) * 100",
        "report_category": "Protection",
        "sub_category": "Child Marriage",
        "indicator_type": "outcome",
        "baseline_value": 45.0,
        "target_value": 20.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "married_before_18", "operator": "==", "value": "yes"},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "school_enrollment_rate",
        "label": "% School-Age Children (6-17) Enrolled in School",
        "description": "Proportion of children 6-17 years currently enrolled in school",
        "unit": "%",
        "formula_text": "count(enrolled == 'yes') / count(age_group IN ['6-17']) * 100",
        "report_category": "Education",
        "sub_category": "Enrollment",
        "indicator_type": "outcome",
        "baseline_value": 65.0,
        "target_value": 85.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "enrolled", "operator": "==", "value": "yes"},
            "denominator": {"field": "age_group", "operator": "==", "value": "6-17"}
        }
    },
    {
        "kpi_code": "primary_completion_rate",
        "label": "% Students Completing Primary School",
        "description": "Proportion of students who completed primary school education",
        "unit": "%",
        "formula_text": "count(primary_completed == 'yes') / count(*) * 100",
        "report_category": "Education",
        "sub_category": "Completion",
        "indicator_type": "outcome",
        "baseline_value": 55.0,
        "target_value": 75.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "primary_completed", "operator": "==", "value": "yes"},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "literacy_rate",
        "label": "% Literacy Rate (Age 15+)",
        "description": "Proportion of adults 15+ years who can read and write",
        "unit": "%",
        "formula_text": "count(literate == 'yes') / count(age >= 15) * 100",
        "report_category": "Education",
        "sub_category": "Literacy",
        "indicator_type": "outcome",
        "baseline_value": 35.0,
        "target_value": 60.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "literate", "operator": "==", "value": "yes"},
            "denominator": {"field": "age", "operator": ">=", "value": 15}
        }
    },
    {
        "kpi_code": "food_insecurity_rate",
        "label": "% Households with Moderate to Severe Food Insecurity",
        "description": "Proportion of households experiencing food insecurity",
        "unit": "%",
        "formula_text": "count(food_security IN ['moderate_insecure', 'severe_insecure']) / count(*) * 100",
        "report_category": "Food Security",
        "sub_category": "Food Insecurity",
        "indicator_type": "outcome",
        "baseline_value": 55.0,
        "target_value": 30.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "food_security", "operator": "in", "value": ["moderate_insecure", "severe_insecure"]},
            "denominator": "*"
        }
    },
    {
        "kpi_code": "income_above_poverty",
        "label": "% Population with Income Above Poverty Line",
        "description": "Proportion of households with income above national poverty line",
        "unit": "%",
        "formula_text": "count(monthly_income > poverty_line) / count(*) * 100",
        "report_category": "Livelihoods",
        "sub_category": "Income",
        "indicator_type": "outcome",
        "baseline_value": 40.0,
        "target_value": 65.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "monthly_income", "operator": ">", "value": 300},  # Example threshold
            "denominator": "*"
        }
    },
    {
        "kpi_code": "employment_rate",
        "label": "% Working-Age Population (15-64) with Employment",
        "description": "Proportion of working-age population currently employed",
        "unit": "%",
        "formula_text": "count(employment == 'employed') / count(age_group IN ['15-64']) * 100",
        "report_category": "Livelihoods",
        "sub_category": "Employment",
        "indicator_type": "outcome",
        "baseline_value": 45.0,
        "target_value": 65.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "employment", "operator": "==", "value": "employed"},
            "denominator": {"field": "age_group", "operator": "==", "value": "15-64"}
        }
    },
    {
        "kpi_code": "business_ownership_rate",
        "label": "% Households with Own Business or Enterprise",
        "description": "Proportion of households with own business/enterprise",
        "unit": "%",
        "formula_text": "count(has_business == 'yes') / count(*) * 100",
        "report_category": "Livelihoods",
        "sub_category": "Business",
        "indicator_type": "outcome",
        "baseline_value": 30.0,
        "target_value": 50.0,
        "is_custom": False,
        "computation_logic": {
            "type": "percentage",
            "numerator": {"field": "has_business", "operator": "==", "value": "yes"},
            "denominator": "*"
        }
    },
]


def seed_kpis():
    """Seed KPI definitions into database."""
    db = SessionLocal()
    
    try:
        print("\n" + "="*70)
        print("SEEDING KPI DEFINITIONS")
        print("="*70)
        
        for kpi_data in STANDARD_KPIS:
            existing = db.query(KPIDefinition).filter(
                KPIDefinition.kpi_code == kpi_data["kpi_code"]
            ).first()
            
            if existing:
                print(f"[SKIP] {kpi_data['kpi_code']} already exists - skipping")
                continue
            
            kpi = KPIDefinition(**kpi_data)
            db.add(kpi)
            print(f"[OK] {kpi_data['kpi_code']:30} | {kpi_data['report_category']:15} | {kpi_data['label'][:45]}")
        
        db.commit()
        
        total_kpis = db.query(KPIDefinition).count()
        print("\n" + "="*70)
        print(f"[OK] KPI Seeding Complete: {total_kpis} KPIs registered")
        print("="*70 + "\n")
        
        return True
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Error seeding KPIs: {e}\n")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = seed_kpis()
    sys.exit(0 if success else 1)
