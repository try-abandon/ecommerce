from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_effective_conversation(self, user_id: str, mode: tuple[str, ...]) -> Conversation | None:
        """
        查找当前用户有效的会话
        有效会话：就是mode属于[AI, QUEUED, HUMAN]
        """
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.mode.in_(mode)
            )
            .order_by(
                Conversation.last_active_at.desc()
            )
            .limit(1)
        )

    async def add_ai_conversation(self, user_id: str) -> Conversation:
        """
        添加ai会话
        """
        conversation = Conversation(user_id=user_id, mode='AI')

        # 添加会话
        self.session.add(conversation)

        # 由于还没有提交数据所以刷新后当前事务可以看到这些更改，而其他事务看不到这个更改
        await self.session.flush()

        return conversation

    async def get_ai_conversation(self, user_id: str) -> Conversation | None:
        """
        获取ai会话
        """
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.mode == "AI"
            )
        )

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """
        根据会话id获得会话
        """
        return await self.session.get(Conversation, conversation_id)
