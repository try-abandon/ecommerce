from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Message, Conversation


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

    async def find_same_message_in_collection(self, message_id: str) -> tuple[Message, Conversation] | None:
        """
        查找当前会话是否有相同的消息
        """
        result = await self.session.execute(
            select(Message, Conversation)
            .join(
                Conversation,
                Message.conversation_id == Conversation.id
            )
            .where(Message.message_id == message_id)
        )

        return result.tuples().one_or_none()

    def add_message(self, message: Message):
        self.session.add(message)
