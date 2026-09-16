from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.message import MessageRepository
from app.repositories.turn import ConversationTurnRepository
from app.services.chat.message import MessageService
from common.config import Settings
from common.utils import get_utcnow
from models.models import Message, Conversation, ConversationTurn


class TurnService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = Settings()
        self.turn_repository = ConversationTurnRepository(session)
        self.message_repository = MessageRepository(session)

    async def add_message_to_turn(
            self,
            message: Message,
            conversation: Conversation
    ) -> ConversationTurn:
        """
        将消息保存到turn中
        查询当前会话的轮次状态是不是RUNNING状态
        如果是RUNNING状态，代表轮次已经被turn_worker领取走，准备交给AI_SERVICE处理--做法：创建一个新的轮次Turn
        如果是COLLECTION状态，代表轮次还没被turn_worker领取走，交给AI_SERVICE处理--做法： 修改这一轮的收集事件。collect_until
        """
        conversation.input_revision += 1
        message.input_revision = conversation.input_revision

        # 1、先查询正在收集会话轮次
        turn = await self.turn_repository.find_collecting_turn_by_conversation_id(conversation.id)

        # 2、查询到就返回轮次
        now = get_utcnow()
        delay = timedelta(milliseconds=self.settings.message_merge_delay_ms)
        if turn:
            # 修改turn的collect_until
            turn.collect_until = min(
                now + delay,
                turn.max_collect_until
            )

            # 返回
            return turn

        # 3、没有查到就创建
        turn = ConversationTurn(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            status="COLLECTING",
            collect_until=now + delay,
            start_revision=conversation.input_revision + 1,
            max_collect_until=now + timedelta(milliseconds=self.settings.message_merge_max_wait_ms)
        )

        self.turn_repository.add_turn(turn)

        return turn

    async def claim_turn(self, worker_id: str) -> ConversationTurn | None:
        """
        从数据库查询到一个turn
        """
        now = get_utcnow()

        # 1、查询可以被领取的turn
        claimed_turn_and_conversation = await self.turn_repository.find_claimed_turn_and_conversation(now)

        # 2、如果没有找到返回None
        if claimed_turn_and_conversation is None:
            return None

        # 3、找到turn，并更新turn中的属性
        claimed_turn, conversation = claimed_turn_and_conversation
        claimed_turn.status = "RUNNING"
        claimed_turn.snapshot_revision = conversation.input_revision
        claimed_turn.locked_by = worker_id
        claimed_turn.locked_until = now + timedelta(self.settings.ai_worker_lease_seconds)
        claimed_turn.attempts += 1
        claimed_turn.started_at = claimed_turn.started_at or now

        # 4、返回
        return claimed_turn

    async def build_ai_request_data(self, claimed_turn: ConversationTurn) -> tuple[dict[str, Any], str]:
        """
        通过领取到的轮次得到当前消息和历史消息
        当前消息：这个轮次里的消息
        历史消息：当前会话中当前消息之前的消息
        """
        # 1、获取当前消息，通过取得快照版本得到这个轮次的消息
        snapshot_revision = claimed_turn.snapshot_revision

        current_messages = await self.message_repository.find_current_message_in_claimed_turn(
            claimed_turn.conversation_id,
            claimed_turn.start_revision,
            snapshot_revision
        )

        # 2、获取历史消息
        history_messages = list(reversed(
            await self.message_repository.find_history_message_by_sequence(claimed_turn.conversation_id,
                                                                           current_messages[0].id)))

        # 3、构建字典，返回上下文
        return {
            "conversation_id": claimed_turn.conversation_id,
            "user_id": claimed_turn.user_id,
            "turn_id": claimed_turn.id,
            "request_id": f"{claimed_turn.id}:attempt:{claimed_turn.attempts}",
            "input_revision": snapshot_revision,
            "messages": [
                {
                    "message_id": message.message_id,
                    "type": message.message_type,
                    "content": message.content,
                }
                for message in current_messages
            ],
            "history": [
                {
                    "message_id": message.message_id,
                    "role": message.role,
                    "type": message.message_type,
                    "content": message.content,
                    "created_at": message.created_at.isoformat()
                }
                for message in history_messages
            ],
        }, current_messages[-1].message_id

    async def find_turn_and_conversation_by_turn_id(self, turn_id: str) -> tuple[ConversationTurn, Conversation]:
        return await self.turn_repository.find_turn_and_conversation_by_turn_id(turn_id)

    def status_superseded(self, turn: ConversationTurn):
        turn.status = "SUPERSEDED"  # 终态
        turn.finished_at = get_utcnow()
        TurnService._release_lease(turn)  # 清理占用者的信息

    @staticmethod
    def _release_lease(turn: ConversationTurn):
        turn.locked_by = None
        turn.locked_until = None
