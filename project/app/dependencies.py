from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthService
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