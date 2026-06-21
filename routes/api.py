import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, Config
import instagram

logger = logging.getLogger("api")
router = APIRouter(prefix="/api")


# ---------- Schemas ----------

class ConfigIn(BaseModel):
    access_token: str
    page_id: Optional[str] = None
    ig_business_account_id: str


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    reply_text: str
    dm_text: str
    active: bool = True


# ---------- Config ----------

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        return {}
    return {
        "access_token": _mask(config.access_token),
        "page_id": config.page_id,
        "ig_business_account_id": config.ig_business_account_id,
    }


@router.post("/config")
def save_config(body: ConfigIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        config = Config()
        db.add(config)
    config.access_token = body.access_token
    config.page_id = body.page_id
    config.ig_business_account_id = body.ig_business_account_id
    db.commit()
    return {"status": "saved"}


def _mask(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    return token[:6] + "..." + token[-4:] if len(token) > 12 else "•" * len(token)


# ---------- Campaigns ----------

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "post_id": c.post_id,
            "post_thumbnail_url": c.post_thumbnail_url,
            "post_caption": c.post_caption,
            "keywords": c.keywords,
            "reply_text": c.reply_text,
            "dm_text": c.dm_text,
            "active": c.active,
        }
        for c in campaigns
    ]


@router.post("/campaigns")
def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    thumbnail_url, caption = None, None

    if config and config.access_token:
        try:
            details = instagram.get_post_details(body.post_id, config.access_token)
            thumbnail_url = details.get("thumbnail_url")
            caption = details.get("caption")
        except Exception:
            logger.exception("Could not fetch post details for %s", body.post_id)

    campaign = Campaign(
        post_id=body.post_id,
        post_thumbnail_url=thumbnail_url,
        post_caption=caption,
        keywords=body.keywords,
        reply_text=body.reply_text,
        dm_text=body.dm_text,
        active=body.active,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {"status": "created", "id": campaign.id}


@router.get("/post-preview/{post_id}")
def post_preview(post_id: str, db: Session = Depends(get_db)):
    """Used by the dashboard's on-blur preview fetch."""
    config = db.query(Config).first()
    if not config or not config.access_token:
        raise HTTPException(status_code=400, detail="Save Instagram credentials first.")
    try:
        return instagram.get_post_details(post_id, config.access_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignIn, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.post_id = body.post_id
    campaign.keywords = body.keywords
    campaign.reply_text = body.reply_text
    campaign.dm_text = body.dm_text
    campaign.active = body.active
    db.commit()
    return {"status": "updated"}


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.active = not campaign.active
    db.commit()
    return {"status": "ok", "active": campaign.active}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}
