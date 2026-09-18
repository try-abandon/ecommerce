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

    async def find_current_message_in_claimed_turn(
            self,
            conversation_id: str,
            start_revision: int,
            snapshot_revision: int | None
    ) -> list[Message]:
        """
        在可领取的轮次找到当前消息的列表
        """
        result = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.input_revision >= start_revision,
                Message.input_revision <= snapshot_revision,
                Message.role == "user"
            )
            .order_by(Message.input_revision)
        )

        return list(result.all())

    async def find_history_message_by_sequence(
            self,
            conversation_id: str,
            message_id: int,
            limit: int = 30
    ) -> list[Message]:
        results = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id < message_id
            )
            .order_by(Message.id.desc())
            .limit(limit)
        )

        return list(results.all())

    async def list_user_history(
            self,
            user_id: str,
            after_sequence: int | None = None
    ) -> list[tuple[Message, Conversation]]:
        """查询当前用户的历史消息，可按消息序号增量读取"""
        statement = (
            select(Message, Conversation)
            .join(
                Conversation,
                Conversation.id == Message.conversation_id,
            )
            .where(Conversation.user_id == user_id)
        )
        if after_sequence is not None:
            statement = statement.where(Message.id > after_sequence)

        result = await self.session.execute(
            statement.order_by(Message.id)
        )
        return list(result.tuples().all())