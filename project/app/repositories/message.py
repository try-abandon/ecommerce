from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        """
        获得会话的消息列表
        """
        result = await self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
        )

        return list(result.all())
