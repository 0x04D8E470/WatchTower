from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db.models.request_template import RequestTemplate
from app.db.models.request_history import RequestHistory

class RequestRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Шаблоны
    async def save_template(
        self,
        user_id: int,
        name: str,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        body_type: str = "raw",
    ) -> RequestTemplate:
        existing = await self.get_template_by_name(user_id, name)
        if existing:
            raise ValueError("Шаблон с таким именем уже существует")
        template = RequestTemplate(
            user_id=user_id,
            name=name,
            method=method,
            url=url,
            headers=headers,
            body=body,
            body_type=body_type,
        )
        self.session.add(template)
        try:
            await self.session.commit()
        except IntegrityError:  # на случай гонки
            await self.session.rollback()
            raise ValueError("Шаблон с таким именем уже существует")
        await self.session.refresh(template)
        return template

    async def get_templates_by_user(self, user_id: int) -> List[RequestTemplate]:
        stmt = select(RequestTemplate).where(RequestTemplate.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_template_by_name(self, user_id: int, name: str) -> Optional[RequestTemplate]:
        stmt = select(RequestTemplate).where(
            RequestTemplate.user_id == user_id,
            RequestTemplate.name == name,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_template(self, template: RequestTemplate) -> None:
        await self.session.delete(template)
        await self.session.commit()

    # История
    async def add_history(self, entry: RequestHistory) -> RequestHistory:
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def get_history_by_user(self, user_id: int, limit: int = 10) -> List[RequestHistory]:
        stmt = (
            select(RequestHistory)
            .where(RequestHistory.user_id == user_id)
            .order_by(RequestHistory.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())