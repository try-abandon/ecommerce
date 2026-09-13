from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession

from common.config import get_settings

# 创建数据库引擎
db_engine: AsyncEngine = create_async_engine(
    url=get_settings().database_url,
    echo=False
)

# 创建异步会话工厂
session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=db_engine,
    expire_on_commit=False  # 异步数据库必须设置为False，将提交后的“过期”机制取消，否则一旦提交的数据过期无法在内存中找到那么就会直接报错
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    在fast_api处理路由请求的时候调用，方法返回的session必须用yield不能用return
    :return:
    """
    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
