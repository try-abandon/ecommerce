from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import ConversationTurn


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
