from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Config(Base):
    """Singleton-ish table storing Instagram credentials. We just keep row id=1."""
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String, nullable=True)
    page_id = Column(String, nullable=True)
    ig_business_account_id = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String, nullable=False, index=True)
    post_thumbnail_url = Column(String, nullable=True)
    post_caption = Column(Text, nullable=True)
    keywords = Column(String, nullable=False)  # comma-separated
    reply_text = Column(Text, nullable=False)
    dm_text = Column(Text, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String, unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
