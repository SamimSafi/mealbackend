"""Tests for ETL pipeline."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from models import Form, Submission
from etl import ETLPipeline


def test_clean_submission_data(db):
    """Test cleaning submission data."""
    etl = ETLPipeline(db)
    
    submission = {
        "field1": "value1",
        "nested": {"field2": "value2"},
        "list_field": [{"item": "data"}],
    }
    
    cleaned = etl.clean_submission_data(submission)
    assert "field1" in cleaned
    assert "nested_field2" in cleaned
    assert "list_field_count" in cleaned


def test_extract_location(db):
    """Test location extraction."""
    etl = ETLPipeline(db)
    
    # Test with geolocation array
    submission1 = {"_geolocation": [40.7128, -74.0060]}
    lat, lng, name = etl.extract_location(submission1)
    assert lat == 40.7128
    assert lng == -74.0060
    
    # Test with geolocation dict
    submission2 = {"geolocation": {"latitude": 40.7128, "longitude": -74.0060}}
    lat, lng, name = etl.extract_location(submission2)
    assert lat == 40.7128
    assert lng == -74.0060


@patch("etl.KoboClient")
def test_sync_form(mock_kobo_client, db):
    """Test syncing a form."""
    # Mock Kobo client
    mock_client = Mock()
    mock_client.get_form.return_value = {
        "id": "test_form_123",
        "title": "Test Form",
        "description": "Test Description",
    }
    mock_client.get_form_submissions.return_value = [
        {
            "_id": "sub1",
            "_submission_time": "2024-01-01T00:00:00Z",
            "field1": "value1",
        }
    ]
    
    etl = ETLPipeline(db, kobo_client=mock_client)
    
    sync_log = etl.sync_form("test_form_123", sync_type="incremental")
    
    assert sync_log.status == "success"
    assert sync_log.records_added == 1
    
    # Check form was created
    form = db.query(Form).filter(Form.kobo_form_id == "test_form_123").first()
    assert form is not None
    assert form.title == "Test Form"
    
    # Check submission was created
    submission = db.query(Submission).filter(Submission.kobo_submission_id == "sub1").first()
    assert submission is not None


def test_compute_indicators(db):
    """Test indicator computation."""
    # Create a form
    form = Form(
        kobo_form_id="test_form",
        title="Test Form",
        form_schema={},
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    
    # Create submissions
    for i in range(5):
        submission = Submission(
            form_id=form.id,
            kobo_submission_id=f"sub{i}",
            submission_data={
                "field1": "value1" if i % 2 == 0 else "value2",
                "numeric_field": i * 10,
                "yes_no": "yes" if i < 3 else "no",
            },
        )
        db.add(submission)
    db.commit()
    
    etl = ETLPipeline(db)
    indicators = etl.compute_indicators(form.id)
    
    assert len(indicators) > 0
    # Should have total count indicator
    count_ind = next((ind for ind in indicators if ind.name == "Total Submissions"), None)
    assert count_ind is not None
    assert count_ind.value == 5

