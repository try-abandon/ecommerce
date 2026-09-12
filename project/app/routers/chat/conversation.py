from typing import Annotated

from fastapi import APIRouter, Header

from project.app.dependencies import ConversationServiceDep

router = APIRouter(prefix="api/v1", tags=["聊天会话"])

@router.post("/conversations/current")
async def get_current_conversation(conversation_service: ConversationServiceDep,
                                   authorization=Annotated[str | None, Header()]):
    """
    权限限制：
    1. 对应的用户信息
    2. 用户身份角色是否是接口允许的角色("customer")
    :param conversation_service:
    :param authorization:
    :return:
    """
    result = conversation_service.get_current_conversation()
    return result