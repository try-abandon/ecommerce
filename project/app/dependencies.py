from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin.auth import AuthService
from app.services.admin.handoff import HandoffService
from app.services.chat.message import MessageService
from app.services.chat.turn import TurnService
from app.services.realtime import RealTimeOutBoxService
from infrastructure.db import get_db_session
from project.app.services.chat.conversation import ConversationService


def get_auth_service():
    """
    获取用户认证服务
    :return:
    """
    return AuthService()


def get_conversation_service(session: Annotated[AsyncSession, Depends(get_db_session)]):
    """
    获取会话服务
    :return:
    """
    return ConversationService(session=session)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


def get_turn_service(session: Annotated[AsyncSession, Depends(get_db_session)]):
    return TurnService(session=session)


TurnServiceDep = Annotated[TurnService, Depends(get_turn_service)]


def get_realtime_outbox_service(session: Annotated[AsyncSession, Depends(get_db_session)]):
    return RealTimeOutBoxService(session=session)


RealTimeOutBoxServiceDep = Annotated[RealTimeOutBoxService, Depends(get_realtime_outbox_service)]


def get_message_service(
        session: Annotated[AsyncSession, Depends(get_db_session)],
        conversation_service: ConversationServiceDep,
        turn_service: TurnServiceDep,
        outbox_service: RealTimeOutBoxServiceDep
):
    return MessageService(
        session,
        conversation_service,
        outbox_service,
        turn_service
    )


MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]


async def get_handoff_service(
        session: Annotated[AsyncSession, Depends(get_db_session)]
) -> HandoffService:
    return HandoffService(session)


HandoffServiceDep = Annotated[HandoffService, Depends(get_handoff_service)]
