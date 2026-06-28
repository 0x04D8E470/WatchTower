from datetime import datetime
from sqlalchemy import BigInteger, String, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class RequestHistory(Base):
    __tablename__ = "request_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("request_templates.id"), nullable=True)
    method: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(nullable=True)
    response_preview: Mapped[str | None] = mapped_column(String, nullable=True)  # обрезанный ответ
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())