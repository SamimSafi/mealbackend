"""KoboToolbox API client."""
import logging
from typing import Any, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class KoboClient:
    """Client for interacting with KoboToolbox API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
    ):
        """Initialize Kobo client."""
        self.api_url = api_url or settings.KOBO_API_URL
        self.api_token = api_token or settings.KOBO_API_TOKEN
        self.username = username or settings.KOBO_USERNAME
        self.headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make an API request."""
        url = f"{self.api_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Kobo API request failed: {method} {url} - {e}")
            raise

    def get_forms(self) -> list[dict[str, Any]]:
        """Get all forms (assets in KoboToolbox API)."""
        try:
            response = self._make_request("GET", "/assets")
            return response.get("results", [])
        except Exception as e:
            logger.error(f"Failed to fetch forms: {e}")
            return []

    def get_form(self, form_id: str) -> Optional[dict[str, Any]]:
        """Get a specific form by ID."""
        try:
            return self._make_request("GET", f"/assets/{form_id}")
        except Exception as e:
            logger.error(f"Failed to fetch form {form_id}: {e}")
            return None

    def get_form_submissions(
        self, form_id: str, limit: int = 1000, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get submissions for a form (data endpoint in KoboToolbox)."""
        try:
            response = self._make_request(
                "GET",
                f"/assets/{form_id}/data",
                params={"limit": limit, "start": offset},
            )
            return response.get("results", [])
        except Exception as e:
            logger.error(f"Failed to fetch submissions for form {form_id}: {e}")
            return []

    def get_all_form_submissions(self, form_id: str) -> list[dict[str, Any]]:
        """Get all submissions for a form (handles pagination)."""
        all_submissions = []
        limit = 1000
        offset = 0

        while True:
            submissions = self.get_form_submissions(form_id, limit=limit, offset=offset)
            if not submissions:
                break
            all_submissions.extend(submissions)
            if len(submissions) < limit:
                break
            offset += limit

        return all_submissions

    def get_submission(self, form_id: str, submission_id: str) -> Optional[dict[str, Any]]:
        """Get a specific submission."""
        try:
            return self._make_request("GET", f"/assets/{form_id}/data/{submission_id}")
        except Exception as e:
            logger.error(f"Failed to fetch submission {submission_id}: {e}")
            return None

