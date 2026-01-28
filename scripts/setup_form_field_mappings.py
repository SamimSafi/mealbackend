"""
Setup script to configure field mappings for reports.

This allows you to explicitly map form fields to standard dimensions
(age, gender, location, etc.) for each form.

Child Protection & Education forms often have different field names,
so this configuration is important for demographics and geo reports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from database import get_db, init_db
from models import Form as FormModel, FormFieldMapping


def setup_mappings():
    """Interactive setup of field mappings for each form."""
    db = next(get_db())
    
    forms = db.query(FormModel).all()
    
    if not forms:
        print("No forms found in database. Sync forms from Kobo first.")
        return
    
    print("\n" + "="*70)
    print("FORM FIELD MAPPING SETUP")
    print("="*70)
    print("\nThis tool helps map your form fields to standard dimensions.")
    print("This is important for demographics and geographic reports.\n")
    
    for form in forms:
        print(f"\nForm: {form.title} (ID: {form.id})")
        print("-" * 70)
        
        existing_mapping = db.query(FormFieldMapping).filter(
            FormFieldMapping.form_id == form.id
        ).first()
        
        if existing_mapping:
            print(f"✓ Mapping already exists")
            update = input("Update mapping? (y/n): ").lower()
            if update != 'y':
                continue
        
        print("\nAvailable fields in form schema:")
        if form.form_schema:
            survey = form.form_schema.get("content", {}).get("survey", [])
            for i, q in enumerate(survey[:15], 1):
                name = q.get("name")
                label = q.get("label", [""])[0] if isinstance(q.get("label"), list) else q.get("label")
                print(f"  {i}. {name:30} → {label}")
            if len(survey) > 15:
                print(f"  ... and {len(survey) - 15} more fields")
        
        print("\nEnter field names for demographics (or leave blank to auto-detect):")
        
        age_field = input("  Age field (e.g., 'demographics/age'): ").strip() or None
        gender_field = input("  Gender field (e.g., 'demographics/gender'): ").strip() or None
        hh_size_field = input("  Household size field (e.g., 'beneficiary/hh_size'): ").strip() or None
        location_field = input("  Location field (e.g., 'location/district'): ").strip() or None
        province_field = input("  Province field (e.g., 'info/province', 'info/wilayat'): ").strip() or None
        district_field = input("  District field (e.g., 'info/district', 'info/wuleswali'): ").strip() or None
        
        if existing_mapping:
            existing_mapping.age_field = age_field or existing_mapping.age_field
            existing_mapping.gender_field = gender_field or existing_mapping.gender_field
            existing_mapping.household_size_field = hh_size_field or existing_mapping.household_size_field
            existing_mapping.location_field = location_field or existing_mapping.location_field
            existing_mapping.province_field = province_field or existing_mapping.province_field
            existing_mapping.district_field = district_field or existing_mapping.district_field
            db.commit()
            print("✓ Mapping updated")
        else:
            mapping = FormFieldMapping(
                form_id=form.id,
                age_field=age_field,
                gender_field=gender_field,
                household_size_field=hh_size_field,
                location_field=location_field,
                province_field=province_field,
                district_field=district_field,
            )
            db.add(mapping)
            db.commit()
            print("✓ Mapping created")
    
    print("\n" + "="*70)
    print("Setup complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    setup_mappings()
