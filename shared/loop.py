"""Python 3.14 compatibility for uAgents.

uagents.Agent() calls asyncio's get_event_loop() in its constructor. Since Python 3.14 that
raises "There is no current event loop" unless one has been set, so every agent module calls
ensure_event_loop() right before creating its Agent.
"""

import asyncio


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if not loop.is_closed():
            return loop
    except RuntimeError:
        pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
