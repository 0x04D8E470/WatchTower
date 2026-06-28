from datetime import datetime
from sqlalchemy import BigInteger, String, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class RequestTemplate(Base):
    __tablename__ = "request_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String, unique=True)  # уникальное имя для пользователя
    method: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    body_type: Mapped[str] = mapped_column(String, default="raw")  # raw, json, form
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())