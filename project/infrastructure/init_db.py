from project.common.event_loop import run_async
from project.infrastructure.db import db_engine
from project.models import models as _models  # noqa: F401
from project.models.models import Base


async def init_database() -> None:
    """创建当前服务 ORM 模型声明的数据库表和索引。"""
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    run_async(init_database())
