import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Request, Query, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, ProcessedComment, Config
import instagram

logger = logging.getLogger("webhook")
router = APIRouter()

WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")


@router.get("/webhook/instagram")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta calls this once when you configure the webhook in the App Dashboard."""
    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        FACEBOOK_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    received = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected, received)


@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if FACEBOOK_APP_SECRET and not _verify_signature(raw_body, signature):
        logger.warning("Invalid webhook signature.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    logger.info("Webhook payload received: %s", payload)

    config = db.query(Config).first()
    if not config or not config.access_token:
        logger.error("No Instagram config saved yet — ignoring webhook event.")
        return {"status": "ignored", "reason": "no config"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            comment_id = value.get("id")
            comment_text = (value.get("text") or "").lower()
            media_id = value.get("media", {}).get("id")

            if not comment_id or not media_id:
                continue

            # Deduplication
            if db.query(ProcessedComment).filter_by(comment_id=comment_id).first():
                logger.info("Comment %s already processed, skipping.", comment_id)
                continue

            campaigns = (
                db.query(Campaign)
                .filter(Campaign.post_id == media_id, Campaign.active == True)  # noqa: E712
                .all()
            )

            for campaign in campaigns:
                keywords = [k.strip().lower() for k in campaign.keywords.split(",") if k.strip()]
                if any(kw in comment_text for kw in keywords):
                    _handle_match(db, config, campaign, comment_id, value)
                    break

    return {"status": "ok"}


def _handle_match(db, config: Config, campaign: Campaign, comment_id: str, value: dict):
    try:
        instagram.reply_to_comment(comment_id, campaign.reply_text, config.access_token)
    except Exception:
        logger.exception("Failed to reply to comment %s", comment_id)

    try:
        commenter_id = value.get("from", {}).get("id") or instagram.get_commenter_user_id(
            comment_id, config.access_token
        )
        if commenter_id:
            instagram.send_dm(
                commenter_id, campaign.dm_text, config.ig_business_account_id, config.access_token
            )
    except Exception:
        logger.exception("Failed to send DM for comment %s", comment_id)

    db.add(ProcessedComment(comment_id=comment_id, campaign_id=campaign.id))
    db.commit()
