import asyncio
import selectors
from collections.abc import Coroutine


def run_async[ResultT](
        core: Coroutine
) -> ResultT:
    return asyncio.run(
        core,
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    )
