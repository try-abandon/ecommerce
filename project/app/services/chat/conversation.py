from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.repositories.turn import ConversationTurnRepository
from common.config import get_settings
from common.utils import get_utcnow
from models.models import Conversation, Message


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversation_repository = ConversationRepository(session)
        self.turn_repository = ConversationTurnRepository(session)
        self.message_repository = MessageRepository(session)

    async def get_current_conversation(self, user_id: str) -> dict[str, Any]:
        """
        获取当前会话
        :return:
        """
        # 1、确保当前用户具有有效的会话
        conversation = await self.ensure_effective_conversion(user_id)

        # 2、当前是否有轮消息
        is_processing = self.turn_repository.is_activate_turn(conversation.id)

        # 3、提交数据
        await self.session.commit()

        # 4、返回接口数据模型的格式字典
        return {
            "id": conversation.id,
            "mode": conversation.mode,
            "is_processing": is_processing
        }

    async def ensure_effective_conversion(self, user_id: str) -> Conversation:
        """
        1、将当前用户已经超时过期的会话将状态设置为“CLOSE”
        2、确保当前用户的会话存在
        """
        # 1、关闭当前用户已经超时过期的会话
        await self._close_timeout_conversation(user_id)

        # 2、查询当前用户是否存在一个有效会话，如果有那么就直接返回
        conversation = await self.conversation_repository.find_effective_conversation(
            user_id,
            ("AI", "QUEUED", "HUMAN")
        )

        if conversation:
            return conversation

        # 3、没有有效会话就创建一个有效的会话
        return await self._create_ai_conversation(user_id)

    async def _create_ai_conversation(self, user_id: str) -> Conversation:
        return await self.conversation_repository.add_ai_conversation(user_id)

    async def _close_timeout_conversation(self, user_id: str):
        """
        将当前用户已经超时过期的会话将状态设置为“CLOSE”
        """
        # 1、获得当前用户的ai会话
        conversation = await self.conversation_repository.get_ai_conversation(user_id)

        # 2、如果存在ai会话就判断是否超时，如果超时就关闭
        if conversation is not None:
            flag = False
            if _has_idle_timeout(conversation):
                conversation.mode = "CLOSE"
                conversation.ended_at = conversation.last_active_at
                flag = True
            if flag:
                await self.session.flush()

    async def get_conversation_detail(self, conversation_id: str) -> dict[str, list[dict[str, Any]]]:
        """
        获取用户会话下的内容
        """
        # 1、根据会话id获取会话
        conversation = await self.conversation_repository.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError("当前用户会话不存在")

        # 2、获取会话消息列表
        conversation_messages = await self.message_repository.get_conversation_messages(conversation_id)

        return {
            "messages": [get_message_payload(message) for message in conversation_messages]
        }


def get_message_payload(message: Message) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at
    }


def _has_idle_timeout(conversation: Conversation) -> bool:
    """
    判断会话是否超时
    """
    # 1、获取当前时间
    current_time = get_utcnow()

    # 2、获取会话中最后一条消息的时间
    last_time = conversation.last_active_at

    # 3、判断是否超时
    timeout = timedelta(minutes=get_settings().conversation_idle_timeout_minutes)

    return (current_time - last_time) >= timeout
