from datetime import datetime

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import ConversationTurn, Conversation


class ConversationTurnRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_activate_turn(self, conversation_id: str) -> bool:
        return bool(await self.session.scalar(
            select(
                exists()
                .where(ConversationTurn.conversation_id == conversation_id,
                       ConversationTurn.status.in_(["COLLECTING", "RUNNING"]))
            )
        ))

    async def find_collecting_turn_by_conversation_id(self, conversation_id: str) -> ConversationTurn | None:
        return await self.session.scalar(
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation_id,
                   ConversationTurn.status == "COLLECTING")
            .with_for_update()
        )

    def add_turn(self, turn: ConversationTurn):
        self.session.add(turn)

    async def find_claimed_turn_and_conversation(self, now: datetime) -> tuple[ConversationTurn, Conversation] | None:
        """
        领取条件：
        1、turn状态是COLLECTING
        2、turn的时间是否比当前时间小
        3、会话模式是AI
        """
        result = await self.session.execute(
            select(ConversationTurn, Conversation)
            .join(
                Conversation,
                ConversationTurn.conversation_id == Conversation.id
            )
            .where(
                ConversationTurn.status == "COLLECTING",
                ConversationTurn.collect_until <= now,
                Conversation.mode == "AI"
            )
            .order_by(ConversationTurn.collect_until, ConversationTurn.created_at)
            .limit(1)
            .with_for_update()
        )

        return result.tuples().one_or_none()

    async def find_turn_and_conversation_by_turn_id(self, turn_id: str) -> tuple[ConversationTurn, Conversation]:
        result = await self.session.execute(
            select(ConversationTurn, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationTurn.conversation_id
            )
            .where(ConversationTurn.id == turn_id)
            .with_for_update(of=Conversation)
        )
        return result.tuples().one()

    async def list_expired_running_turns(
            self,
            now: datetime
    ) -> list[ConversationTurn]:
        """查询租约已经过期的全部运行中 Turn。"""
        result = await self.session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.status == "RUNNING",
                ConversationTurn.locked_until <= now
            )
        )
        return list(result.all())
