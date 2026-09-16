import asyncio
import logging
import os
import socket
from typing import Any

from app.schemas.user import CurrentUser
from app.services.auth import AuthService
from app.services.chat.turn import TurnService
from common.config import get_settings, Settings
from infrastructure.db import session_factory
from worker.ai.gateway import AIServiceGateway
from worker.ai.parser import AIEventParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TurnProcessor:
    """
    轮次处理器
    """

    def __init__(self):
        self.setting = get_settings()
        self.auth_service = AuthService()
        self.ai_gateway = AIServiceGateway()
        self.event_parser = AIEventParser()

    async def process(self, request_data: dict[str, Any], request_message_id: str):
        # 1、创建令牌
        access_token = self.auth_service.encode_access_token(CurrentUser(user_id=request_data['user_id']))

        # 2、(发送请求给AI_SERVICE/解析AI_SERVICE的事件类型以及数据/校验【二阶段】)
        error: Exception | None = None
        run_id: str | None = None
        run_result: dict[str, Any] | None = None
        try:
            run_id, run_result = await self.run_ai_pipeline(access_token, request_data)
        except Exception as exec:
            error = exec
            logger.exception(f"{request_data['turn_id']}运行失败,原因:{exec}")

        # 3、修改Turn状态将结果保存

    async def run_ai_pipeline(
            self,
            access_token: str,
            request_data: dict[str, Any]
    ) -> tuple[str, dict[str, Any] | None] | None:
        # 1、第一阶段调用start_run
        event = await self.ai_gateway.start_run(access_token, request_data)

        # 2、找到run_id
        run_id = self.event_parser.find_run_id(event)

        # 3、根据事件查询事件类型是否是run_decision_prepared
        prepared = self.event_parser.has_prepared_decision(event)

        commit = False
        # 4、决策准备好了
        try:
            if prepared:
                # 校验版本快照是否过期如果过期调用cancel_run,如果没有过期那么调用commit_run
                if not await self.verify_before_commit(request_data['turn_id'], run_id):
                    await self.ai_gateway.cancel_run(access_token, run_id)
                    return run_id, None

                # 调用commit_run
                event = await self.ai_gateway.commit_run(access_token, run_id, request_data['input_revision'])
                commit = True  # 变量

            return run_id, self.event_parser.parser_outcome(event)

        except Exception as exec:
            if prepared and not commit:  # 控制二阶段（cancel 只能针对二阶段）
                await self.ai_gateway.cancel_run(access_token, run_id)
            raise exec

    async def verify_before_commit(self, turn_id: str, run_id: str) -> bool:
        async  with session_factory() as session:
            turn_service = TurnService(session)

            # 1、获取turn_id对应的轮次和所在会话
            turn_and_conversation = await turn_service.find_turn_and_conversation_by_turn_id(turn_id)

            # 2、解包
            turn, conversation = turn_and_conversation

            if run_id:
                turn.run_id = run_id

            # 3、校验
            if turn.snapshot_revision != conversation.input_revision:
                # 将过期的turn的状态改为SUPERSEDED
                turn_service.status_superseded(turn)

                # 更新数据库并释放锁
                await session.commit()

                return False

            await session.commit()
            return True


class AIWorker:
    def __init__(self):
        self.settings = get_settings()
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.session_factory = session_factory
        self.turn_processor = TurnProcessor()

    async def start(self):
        """
        循环执行turn的处理
        """
        while True:
            try:
                # 确定是否领取到turn，如果领取到那么调用turn的处理器
                processed = await self.poll_and_process()

                if not processed:
                    # 领取失败短睡
                    await asyncio.sleep(self.settings.ai_worker_poll_interval_ms / 1000)
            except Exception as e:
                logger.exception(f"{self.worker_id}执行失败了,原因是:{e}")
                # 执行失败长睡
                await asyncio.sleep(1)

    async def poll_and_process(self) -> bool:
        """
        负责领取轮次，领取成功调用轮次处理器处理
        """
        # 1、领取turn
        claimed_turn = await self.claim_turn()

        # 2、如果没有领取到返回False
        if claimed_turn is None:
            return False

        # 3、如果领取到了得到request_data和request_message_id
        request_data, request_message_id = claimed_turn

        # 4、调用轮次处理器
        await self.turn_processor.process(request_data, request_message_id)

        # 5、返回True
        return True

    async def claim_turn(self) -> tuple[dict[str, Any], str] | None:
        """
        领取轮次,并且得到当前信息的上下文信息
        """
        async with self.session_factory() as session:
            turn_service = TurnService(session)
            # 1、领取turn
            claimed_turn = await turn_service.claim_turn(self.worker_id)

            # 2、如果没有领取到返回None
            if claimed_turn is None:
                return None

            # 3、如果领取到那么构建上下文信息
            request_data, request_message_id = await turn_service.build_ai_request_data(claimed_turn)
            await session.commit()

            # 4、返回
            return request_data, request_message_id
