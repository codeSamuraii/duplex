import eventlet
import logging
import asyncio
from functools import wraps, partial

log = logging.getLogger('Duplex')


def eventlet_routine():
    """Patch imports and disable multiple readers warnings."""
    if not eventlet.patcher.is_monkey_patched('socket'):
        log.debug("Patching imports...")
        eventlet.monkey_patch()

        from eventlet import debug as eventlet_debug
        eventlet_debug.hub_prevent_multiple_readers(False)
    else:
        log.debug("All modules patched.")
    

def configure_logging(name: str, level: int = logging.INFO):
    """Create a logger instance with provided name and configure it."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def make_awaitable(func: callable):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run