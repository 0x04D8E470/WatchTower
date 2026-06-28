from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    url: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String, default="GET")
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    check_interval: Mapped[int] = mapped_column(Integer, default=300)  # в секундах
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[Optional[str]] = mapped_column(String, default="unknown")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())