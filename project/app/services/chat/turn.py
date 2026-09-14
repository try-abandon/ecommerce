from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.turn import ConversationTurnRepository
from common.config import Settings
from common.utils import get_utcnow
from models.models import Message, Conversation, ConversationTurn


class TurnService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = Settings()
        self.turn_repository = ConversationTurnRepository(session)

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
