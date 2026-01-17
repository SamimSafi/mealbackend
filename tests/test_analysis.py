import pytest
from datetime import datetime
from models import Form, Submission

def test_get_analysis_filters(client, auth_headers, db):
    # 1. Setup: Create a form with a schema
    form = Form(
        title="Test Analysis Form",
        kobo_form_id="test_form_1",
        form_schema={
            "content": {
                "survey": [
                    {"name": "gender", "type": "select_one", "label": ["Gender"]},
                    {"name": "education", "type": "select_one", "label": ["Education"]},
                    {"name": "comment", "type": "text", "label": ["Comment"]}
                ]
            }
        },
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    # 2. Add some submissions
    sub1 = Submission(
        form_id=form.id,
        kobo_submission_id="sub1",
        location_name="Kabul",
        submission_data={"gender": "male", "education": "university", "_submitted_by": "enum1"},
        cleaned_data={
            "gender": "male",
            "education": "university",
            "_submitted_by": "enum1"
        },
        created_at=datetime(2023, 1, 1)
    )
    sub2 = Submission(
        form_id=form.id,
        kobo_submission_id="sub2",
        location_name="Herat",
        submission_data={"gender": "female", "education": "high_school", "_submitted_by": "enum2"},
        cleaned_data={
            "gender": "female",
            "education": "high_school",
            "_submitted_by": "enum2"
        },
        created_at=datetime(2023, 1, 2)
    )
    db.add_all([sub1, sub2])
    db.commit()

    # 3. Test the endpoint
    response = client.get(f"/api/analysis/filters?form_id={form.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Check categorical fields
    field_names = [f["name"] for f in data["categorical_fields"]]
    assert "gender" in field_names
    assert "education" in field_names
    assert "comment" in field_names  # Now it should be there!
    
    # Check locations
    assert "Kabul" in data["locations"]
    assert "Herat" in data["locations"]
    
    # Check enumerators
    assert "enum1" in data["enumerators"]
    assert "enum2" in data["enumerators"]

def test_crosstab(client, auth_headers, db):
    # Setup same as above
    form = Form(
        title="Test Analysis Form",
        kobo_form_id="test_form_2",
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    subs = [
        Submission(
            form_id=form.id, 
            kobo_submission_id=f"s{i}", 
            submission_data={"g": "m", "e": "u"},
            cleaned_data={"g": "m", "e": "u"}, 
            created_at=datetime.now()
        ) for i in range(3)
    ] + [
        Submission(
            form_id=form.id, 
            kobo_submission_id=f"s{i+3}", 
            submission_data={"g": "f", "e": "h"},
            cleaned_data={"g": "f", "e": "h"}, 
            created_at=datetime.now()
        ) for i in range(2)
    ]
    db.add_all(subs)
    db.commit()

    response = client.get(
        f"/api/analysis/crosstab?form_id={form.id}&row=g&column=e",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["grand_total"] == 5
    assert "m" in data["rows"]
    assert "f" in data["rows"]
    assert "u" in data["columns"]
    assert "h" in data["columns"]

def test_stacked_bar(client, auth_headers, db):
    form = Form(title="T3", kobo_form_id="tf3", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)
    
    sub = Submission(
        form_id=form.id, 
        kobo_submission_id="ts1", 
        submission_data={"x": "a", "s": "b"},
        cleaned_data={"x": "a", "s": "b"}, 
        created_at=datetime.now()
    )
    db.add(sub)
    db.commit()

    response = client.get(
        f"/api/analysis/stacked-bar?form_id={form.id}&x=x&stack=s",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["items"][0]["category"] == "a"
    assert data["items"][0]["values"]["b"] == 1

def test_crosstab_with_extra_filter(client, auth_headers, db):
    form = Form(title="FilterTest", kobo_form_id="ft_filter", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)

    subs = [
        Submission(
            form_id=form.id, 
            kobo_submission_id="f1", 
            submission_data={"g": "m", "e": "u", "p": "kbl"},
            cleaned_data={"g": "m", "e": "u", "p": "kbl"}, 
            created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, 
            kobo_submission_id="f2", 
            submission_data={"g": "m", "e": "u", "p": "hrt"},
            cleaned_data={"g": "m", "e": "u", "p": "hrt"}, 
            created_at=datetime.now()
        )
    ]
    db.add_all(subs)
    db.commit()

    # Filter by p=kbl
    response = client.get(
        f"/api/analysis/crosstab?form_id={form.id}&row=g&column=e&filter_field=p&filter_value=kbl",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grand_total"] == 1
    assert data["total_responses"] == 1 # total_responses also gets filtered by _apply_filters


def test_numeric_summary(client, auth_headers, db):
    # 1. Setup: Create a form with a numeric field
    form = Form(
        title="Test Numeric Form",
        kobo_form_id="test_numeric_1",
        form_schema={
            "content": {
                "survey": [
                    {"name": "household_size", "type": "integer", "label": ["Household Size"]},
                    {"name": "income", "type": "decimal", "label": ["Income"]}
                ]
            }
        },
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    # 2. Add some submissions with numeric data
    # Values: 5, 10, 15, 20, null, -5 (should be excluded), "abc" (should be excluded)
    subs = [
        Submission(
            form_id=form.id, kobo_submission_id="ns1", 
            submission_data={"household_size": 5, "income": 1000.5},
            cleaned_data={"household_size": 5, "income": 1000.5}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns2", 
            submission_data={"household_size": 10, "income": 2000.0},
            cleaned_data={"household_size": 10, "income": 2000.0}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns3", 
            submission_data={"household_size": 15, "income": 3000.0},
            cleaned_data={"household_size": 15, "income": 3000.0}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns4", 
            submission_data={"household_size": 20, "income": 4000.0},
            cleaned_data={"household_size": 20, "income": 4000.0}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns5", 
            submission_data={"household_size": None, "income": 5000.0},
            cleaned_data={"household_size": None, "income": 5000.0}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns6", 
            submission_data={"household_size": -5, "income": 6000.0},
            cleaned_data={"household_size": -5, "income": 6000.0}, created_at=datetime.now()
        ),
        Submission(
            form_id=form.id, kobo_submission_id="ns7", 
            submission_data={"household_size": "abc", "income": 7000.0},
            cleaned_data={"household_size": "abc", "income": 7000.0}, created_at=datetime.now()
        ),
    ]
    db.add_all(subs)
    db.commit()

    # 3. Test the endpoint for household_size
    # Valid values: [5, 10, 15, 20]
    # Mean: 12.5, Median: 12.5, Min: 5, Max: 20
    response = client.get(
        f"/api/analysis/numeric-summary?form_id={form.id}&field=household_size",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["field"] == "household_size"
    assert data["valid_count"] == 4
    assert data["excluded_count"] == 3 # None, -5, "abc"
    
    stats = data["statistics"]
    assert stats["mean"] == 12.5
    assert stats["median"] == 12.5
    assert stats["min"] == 5
    assert stats["max"] == 20
    assert "std_dev" in stats
    assert "q1" in stats
    assert "q3" in stats
    assert "iqr" in stats

    # 4. Test error for categorical field
    # Create another form with categorical field
    form_cat = Form(
        title="Cat Form", kobo_form_id="test_cat",
        form_schema={"content": {"survey": [{"name": "gender", "type": "select_one"}]}},
        is_active=True
    )
    db.add(form_cat)
    db.commit()
    
    response = client.get(
        f"/api/analysis/numeric-summary?form_id={form_cat.id}&field=gender",
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "not numeric" in response.json()["detail"]
