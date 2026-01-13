#!/usr/bin/env python
"""Check form choices structure."""

from database import SessionLocal
from models import Form as FormModel
import json

db = SessionLocal()

form = db.query(FormModel).filter(FormModel.id == 16).first()

if form and form.form_schema:
    content = form.form_schema.get('content', {})
    choices = content.get('choices', [])
    
    print("Form 16 Choices Structure:")
    print(f"Type: {type(choices)}")
    print(f"Length: {len(choices) if isinstance(choices, (list, dict)) else 'N/A'}")
    
    if isinstance(choices, list):
        print("\nFirst 3 choice items:")
        for item in choices[:3]:
            print(f"  {item}")
    elif isinstance(choices, dict):
        print("\nFirst 3 choice groups:")
        for choice_name, choice_list in list(choices.items())[:3]:
            print(f"\n{choice_name}: {choice_list[:2]}")

db.close()
