from typing import Annotated

from fastapi import APIRouter, Header

from app.schemas.conversation import CurrentConversationResponse, ConversationDetailResponse
from project.app.dependencies import ConversationServiceDep, get_auth_service

router = APIRouter(prefix="/api/v1", tags=["聊天会话"])


@router.post("/conversations/current",
             response_model=CurrentConversationResponse)
async def get_current_conversation(conversation_service: ConversationServiceDep,
                                   authorization: Annotated[str | None, Header()] = None):
    """
    权限限制：
    1. 对应的用户信息
    2. 用户身份角色是否是接口允许的角色("customer")
    :return:
    """
    # 1、获得用户信息
    authorized_user = get_auth_service().get_authorized_user(authorization, "customer")

    # 2、获得接口数据模型的格式字典
    result = conversation_service.get_current_conversation(authorized_user.user_id)

    return result


@router.get("/conversations/{conversation_id}",
            response_model=ConversationDetailResponse)
async def get_conversation_detail(
        conversation_id: str,
        conversation_service: ConversationServiceDep,
        authorization: Annotated[str | None, Header()] = None
):
    # 1、获取用户信息
    authorized_user = get_auth_service().get_authorized_user(authorization, "agent", "admin")

    # 2、获得会话详情
    conversation_detail = conversation_service.get_conversation_detail(conversation_id)

    return conversation_detail
