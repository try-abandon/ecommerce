from typing import Any

from select import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.chat.message import MessageRepository
from app.schemas.chat.message import ChatMessageRequest
from app.schemas.event import RealTimeOutBoxType
from app.services.chat.conversation import ConversationService
from app.services.chat.turn import TurnService
from app.services.realtime import RealTimeOutBoxService, STAFF_CHANNEL, build_message_created_data

from common.utils import get_uid, get_utcnow
from models.models import Conversation, Message


class MessageService:
    def __init__(
            self,
            session: AsyncSession,
            conversation_service: ConversationService,
            outbox_service: RealTimeOutBoxService,
            turn_service: TurnService
    ):
        self.session = session
        self.message_repository = MessageRepository(session)
        self.conversation_service = conversation_service
        self.outbox_service = outbox_service
        self.turn_service = turn_service

    async def accept_user_message(
            self,
            chat_message: ChatMessageRequest,
            user_id: str
    ) -> dict[str, Any]:
        """
        保存用户信息
        """

        # 1、判断当前用户发送的是否是同一条消息
        duplicate_message = await self.message_repository.find_same_message_in_collection(chat_message.message_id)

        ## 1.1、如果有重复的消息直接返回{"conversation_id": "", "mode": "}
        if duplicate_message:
            message, conversation = duplicate_message
            return {
                "conversation_id": message.conversation_id,
                "mode": conversation.mode
            }

        # 2、创建当前用户消息
        # 拿到当前用户的有效会话
        conversation = await self.conversation_service.have_lock_ensure_effective_conversion(user_id)

        # 保存消息
        message = self.save_message(
            conversation,
            chat_message.content,
            chat_message.message_id,
            message_role="user",
            message_type=chat_message.type
        )

        # 3、判断会话模式
        if conversation.mode == "AI":
            ## 3.1、如果是AI模式，那么进入轮次处理
            await self.turn_service.add_message_to_turn(message, conversation)
        elif conversation.mode in ("QUEUED", "HUMAN"):
            ## 3.2、如果是QUEUED或者HUMAN需要管理实时时间事件
            await self.session.flush()
            self.outbox_service.add_message_created_events(
                conversation,
                message,
                notify_user=False,
                notify_staff=True
            )
        else:
            raise ValueError(f"当前会话模式{conversation.mode}不支持")

        # 提交保存
        await self.session.commit()

        # 4、返回接口要的数据{"conversation_id": "", "mode": "}
        return {
            "conversation_id": conversation.id,
            "mode": conversation.mode
        }

    def save_message(self,
                     conversation: Conversation,
                     message_content: dict[str, Any],
                     message_id: str | None,
                     *,
                     message_role: str,
                     message_type: str = "text",
                     ) -> Message:

        # 1. 实例化消息对象
        message = Message(
            conversation_id=conversation.id,
            role=message_role,
            message_id=message_id or get_uid(conversation.id),
            message_type=message_type,
            content=message_content
        )

        # 2. 更新会话的激活时间(判断是否过期)
        conversation.last_active_at = get_utcnow()

        # 3. 保存
        self.message_repository.add_message(message)

        return message

    async def get_history(
            self,
            user_id: str,
            after_sequence: int | None = None
    ) -> list[dict[str, Any]]:
        """返回用户历史消息；重连时可按 sequence 增量查询。"""
        return [
            {
                **build_message_created_data(message),
                "conversation_started_at": conversation.started_at.isoformat()
            }
            for message, conversation in (
                await self.message_repository.list_user_history(
                    user_id,
                    after_sequence
                )
            )
        ]
