"""
autourgos-preiteration — Pre-iteration middleware for Autourgos agents.

Run callbacks and inject files (screenshots, docs) before each agent iteration.
Supports sync and async hooks, sequential and parallel execution, and
automatic image compression to reduce LLM token costs.

Quick start::

    from autourgos_preiteration import PreIterationMiddleware

    middleware = PreIterationMiddleware(
        callback=capture_screenshot,
        files="/tmp/screen.png",
        image_quality="low",
    )
    agent = Agent(llm=my_llm, middleware=[middleware])
"""

from .base import CallbackHandler
from .middleware import (
    SEQUENTIAL,
    PARALLEL,
    PreIterationMiddleware,
    is_async_callable,
)

from autourgos_core import package_version

__version__ = package_version("autourgos-preiteration", fallback="3.0.9")

__all__ = [
    "PreIterationMiddleware",
    "SEQUENTIAL",
    "PARALLEL",
    "CallbackHandler",
    "is_async_callable",
]
