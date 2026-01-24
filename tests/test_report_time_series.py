import pytest
from datetime import datetime, timedelta
import pytz
from models import Form, Submission, UserFormAccess

def test_time_series_report_basic(client, auth_headers, test_user, db):
    # 1. Setup: Create a form and some submissions
    form = Form(
        title="Time Series Test Form",
        kobo_form_id="ts_test_1",
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    # Grant access to test_user
    access = UserFormAccess(user_id=test_user.id, form_id=form.id)
    db.add(access)
    db.commit()

    # Add submissions on different days
    # Jan 1, 2024: 2 subs
    # Jan 2, 2024: 1 sub
    subs = [
        Submission(
            form_id=form.id,
            kobo_submission_id="s1",
            submission_data={},
            created_at=datetime(2024, 1, 1, 10, 0, 0)
        ),
        Submission(
            form_id=form.id,
            kobo_submission_id="s2",
            submission_data={},
            created_at=datetime(2024, 1, 1, 15, 0, 0)
        ),
        Submission(
            form_id=form.id,
            kobo_submission_id="s3",
            submission_data={},
            created_at=datetime(2024, 1, 2, 10, 0, 0)
        )
    ]
    db.add_all(subs)
    db.commit()

    # 2. Test the endpoint
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&start=2024-01-01T00:00:00&end=2024-01-03T00:00:00&group_by=day",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["total_submissions"] == 3
    assert len(data["data"]) >= 2
    
    # Check specific days
    # Note: Backend defaults to Asia/Kabul which is UTC+4:30
    # Jan 1 10:00 UTC -> 14:30 Kabul
    # Jan 2 10:00 UTC -> 14:30 Kabul
    day1 = [d for d in data["data"] if "2024-01-01" in d["label"]]
    day2 = [d for d in data["data"] if "2024-01-02" in d["label"]]
    
    assert len(day1) == 1
    assert day1[0]["count"] == 2
    assert len(day2) == 1
    assert day2[0]["count"] == 1

def test_time_series_year_month_shortcut(client, auth_headers, test_user, db):
    form = Form(title="TS Shortcut", kobo_form_id="ts_2", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)

    # Grant access
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub in Feb 2024
    sub = Submission(
        form_id=form.id,
        kobo_submission_id="s_feb",
        submission_data={},
        created_at=datetime(2024, 2, 15, 12, 0, 0)
    )
    db.add(sub)
    db.commit()

    # Query with year=2024, month=2
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&year=2024&month=2",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_submissions"] == 1
    # month=2 should default group_by to day
    assert data["group_by"] == "day"

def test_time_series_hour_2_alignment(client, auth_headers, test_user, db):
    form = Form(title="TS Hour", kobo_form_id="ts_3", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)

    # Grant access
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub at 13:15 UTC (17:45 Kabul)
    # Should fall into 16:00-18:00 Kabul bucket or similar
    sub = Submission(
        form_id=form.id,
        kobo_submission_id="s_h",
        submission_data={},
        created_at=datetime(2024, 1, 1, 13, 15, 0)
    )
    db.add(sub)
    db.commit()

    # Query with group_by=hour_2
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&start=2024-01-01T00:00:00&end=2024-01-02T00:00:00&group_by=hour_2&tz=UTC",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    # In UTC:
    # 13:15 should be in the 12:00 bucket (if aligned to even hours)
    bucket_12 = [d for d in data["data"] if "12:00" in d["label"]]
    assert len(bucket_12) == 1
    assert bucket_12[0]["count"] == 1

def test_time_series_with_filters(client, auth_headers, test_user, db):
    form = Form(
        title="TS Filter", 
        kobo_form_id="ts_4", 
        is_active=True,
        form_schema={"content": {"survey": [{"name": "info/province", "label": "Province"}]}}
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    # Grant access
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Kabul sub
    sub1 = Submission(
        form_id=form.id,
        kobo_submission_id="sf1",
        submission_data={"info": {"province": "Kabul"}},
        cleaned_data={"info": {"province": "Kabul"}},
        created_at=datetime(2024, 1, 1, 12, 0, 0)
    )
    # Herat sub
    sub2 = Submission(
        form_id=form.id,
        kobo_submission_id="sf2",
        submission_data={"info": {"province": "Herat"}},
        cleaned_data={"info": {"province": "Herat"}},
        created_at=datetime(2024, 1, 1, 12, 0, 0)
    )
    db.add_all([sub1, sub2])
    db.commit()

    # Query filtering by province=Kabul, use mode=all_time to include old data
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&province=Kabul&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_submissions"] == 1
    assert data["field_labels"]["province"] == "Province"

def test_time_series_empty_data_full_range(client, auth_headers, test_user, db):
    form = Form(title="Empty TS", kobo_form_id="ts_empty", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Query a range with NO data
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&start=2024-01-01T00:00:00&end=2024-01-05T00:00:00&group_by=day&tz=UTC",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_submissions"] == 0
    # Should have 4 days (Jan 1, 2, 3, 4) even if empty
    assert len(data["data"]) == 4
    for item in data["data"]:
        assert item["count"] == 0

def test_time_series_year_range_with_zeros(client, auth_headers, test_user, db):
    form = Form(title="Year Range TS", kobo_form_id="ts_year", is_active=True)
    db.add(form)
    db.commit()
    db.refresh(form)
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub in 2024
    sub = Submission(
        form_id=form.id,
        kobo_submission_id="s_2024",
        submission_data={},
        created_at=datetime(2024, 6, 1, 12, 0, 0)
    )
    db.add(sub)
    db.commit()

    # Query 2022 to 2026 (Kabul Time)
    # Kabul is UTC+4:30. 
    # 2021-12-31T19:30:00Z is 2022-01-01T00:00:00 in Kabul
    # 2026-12-31T19:30:00Z is 2027-01-01T00:00:00 in Kabul
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&start=2021-12-31T19:30:00Z&end=2026-12-31T19:29:59Z&group_by=year&tz=Asia/Kabul",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_submissions"] == 1
    # Should have 2022, 2023, 2024, 2025, 2026 (5 years)
    assert len(data["data"]) == 5
    
    years = [d["label"] for d in data["data"]]
    assert "2022" in years
    assert "2024" in years
    assert "2026" in years
    
    val_2024 = [d for d in data["data"] if d["label"] == "2024"][0]
    assert val_2024["count"] == 1
    
    val_2022 = [d for d in data["data"] if d["label"] == "2022"][0]
    assert val_2022["count"] == 0

def test_time_series_all_time_hour_2_filter(client, auth_headers, test_user, db):
    """Verify that all_time mode preserves hour_2 group_by even with filters."""
    form = Form(
        title="All Time Hour 2", 
        kobo_form_id="ts_all_hour", 
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub in Balkh
    sub1 = Submission(
        form_id=form.id,
        kobo_submission_id="sb1",
        submission_data={"info": {"province": "Balkh"}},
        cleaned_data={"info": {"province": "Balkh"}},
        created_at=datetime(2026, 1, 15, 10, 0, 0)
    )
    db.add(sub1)
    db.commit()

    # Query with mode=all_time, group_by=hour_2, province=Balkh
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&mode=all_time&group_by=hour_2&province=Balkh",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["group_by"] == "hour_2"
    assert data["total_submissions"] == 1
    
    # Check that labels are hour-formatted, not month
    # Kabul time for 10:00 UTC is 14:30. 
    # Label should be 2026-01-15 14:00 (if snapped to 2h)
    assert "2026-01-15 14:00" in [d["label"] for d in data["data"]]

def test_time_series_filter_case_insensitive(client, auth_headers, test_user, db):
    """Verify that field filters are case-insensitive."""
    form = Form(
        title="Case Insensitive Test", 
        kobo_form_id="ts_case", 
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub with "Balkh"
    sub = Submission(
        form_id=form.id,
        kobo_submission_id="scase1",
        submission_data={"info": {"province": "Balkh"}},
        cleaned_data={"info": {"province": "Balkh"}},
        created_at=datetime(2024, 1, 1, 10, 0, 0)
    )
    db.add(sub)
    db.commit()

    # Query with "balkh" (lowercase)
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&info/province=balkh&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_submissions"] == 1
    
    # Query with "BALKH" (uppercase)
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&info/province=BALKH&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_submissions"] == 1

def test_time_series_soft_match_sql_optimization(client, auth_headers, test_user, db):
    """Verify soft matching for location_name and top-level field filters (SQL optimized)."""
    form = Form(
        title="Soft Match Optimization Test", 
        kobo_form_id="ts_soft_opt", 
        is_active=True
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    db.add(UserFormAccess(user_id=test_user.id, form_id=form.id))
    db.commit()

    # Sub 1: location_name="Jalal Abad", cleaned_data={"status": "in_progress"}
    sub1 = Submission(
        form_id=form.id,
        kobo_submission_id="soft1",
        location_name="Jalal Abad",
        submission_data={"status": "in_progress"},
        cleaned_data={"status": "in_progress"},
        created_at=datetime(2024, 1, 1, 10, 0, 0)
    )
    # Sub 2: location_name="Kabul", cleaned_data={"status": "completed"}
    sub2 = Submission(
        form_id=form.id,
        kobo_submission_id="soft2",
        location_name="Kabul",
        submission_data={"status": "completed"},
        cleaned_data={"status": "completed"},
        created_at=datetime(2024, 1, 1, 10, 0, 0)
    )
    db.add_all([sub1, sub2])
    db.commit()

    # 1. Test location_name soft match (space vs underscore)
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&province=jalal_abad&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total_submissions"] == 1

    # 2. Test top-level field_filter soft match (case and space vs underscore)
    # Note: query param name must match field name in cleaned_data
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&status=In_Progress&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total_submissions"] == 1

    # 3. Test list in field_filter with mixed formats
    response = client.get(
        f"/api/reports/submissions/time-series?form_id={form.id}&status=in_progress,completed&mode=all_time",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total_submissions"] == 2
