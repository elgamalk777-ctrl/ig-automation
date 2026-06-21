"""
instagram.py — Thin client around the official Instagram Graph API.

No unofficial/third-party automation libraries are used here — only
authenticated HTTPS calls to graph.facebook.com using a long-lived
User/Page Access Token that the user generates themselves via the
Facebook Developer App (see README.md for the full setup walkthrough).
"""
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger("instagram")

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2


class InstagramAPIError(Exception):
    pass


def _request_with_retry(method: str, url: str, **kwargs) -> dict:
    """Perform an HTTP request with exponential backoff on rate-limit / transient errors."""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.request(method, url, **kwargs)

            if resp.status_code == 200:
                logger.info("Graph API %s %s -> 200", method, url)
                return resp.json()

            # Rate limited or transient server error -> retry with backoff
            if resp.status_code in (429, 500, 502, 503):
                wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Graph API %s returned %s (attempt %s/%s). Retrying in %ss. Body: %s",
                    url, resp.status_code, attempt, MAX_RETRIES, wait, resp.text,
                )
                time.sleep(wait)
                continue

            # Non-retryable error
            logger.error("Graph API error %s: %s", resp.status_code, resp.text)
            raise InstagramAPIError(f"Graph API error {resp.status_code}: {resp.text}")

        except httpx.RequestError as exc:
            last_exc = exc
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning("Network error calling %s (attempt %s/%s): %s. Retrying in %ss.",
                           url, attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)

    raise InstagramAPIError(f"Failed after {MAX_RETRIES} attempts: {last_exc}")


def reply_to_comment(comment_id: str, message: str, access_token: str) -> dict:
    """Post a public reply to a comment. POST /{comment-id}/replies"""
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    payload = {"message": message, "access_token": access_token}
    return _request_with_retry("POST", url, data=payload)


def send_dm(instagram_user_id: str, message: str, ig_business_account_id: str, access_token: str) -> dict:
    """
    Send a private DM via the Instagram Send API.
    POST /{ig-business-account-id}/messages

    NOTE: per Meta policy, this only works if the recipient has previously
    messaged the business within the last 24h window, OR your app has been
    approved for the instagram_manage_messages permission with the
    "Human Agent" / comment-triggered messaging use case. See README.
    """
    url = f"{GRAPH_API_BASE}/{ig_business_account_id}/messages"
    payload = {
        "recipient": {"id": instagram_user_id},
        "message": {"text": message},
        "access_token": access_token,
    }
    return _request_with_retry("POST", url, json=payload)


def get_post_details(post_id: str, access_token: str) -> dict:
    """Fetch a post's thumbnail + caption. GET /{ig-media-id}?fields=..."""
    url = f"{GRAPH_API_BASE}/{post_id}"
    params = {
        "fields": "caption,media_type,media_url,thumbnail_url,permalink",
        "access_token": access_token,
    }
    data = _request_with_retry("GET", url, params=params)
    thumbnail = data.get("thumbnail_url") or data.get("media_url")
    return {
        "caption": data.get("caption", ""),
        "thumbnail_url": thumbnail,
        "permalink": data.get("permalink"),
        "media_type": data.get("media_type"),
    }


def get_commenter_user_id(comment_id: str, access_token: str) -> Optional[str]:
    """Resolve the Instagram-scoped user ID of whoever left a comment."""
    url = f"{GRAPH_API_BASE}/{comment_id}"
    params = {"fields": "from", "access_token": access_token}
    data = _request_with_retry("GET", url, params=params)
    return data.get("from", {}).get("id")
