"""
middleware.py — SEQUENTIAL, PARALLEL, and PreIterationMiddleware.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
import os
import tempfile
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from .base import CallbackHandler


# ── helpers ────────────────────────────────────────────────────────────────────

def is_async_callable(obj: Any) -> bool:
    if obj is None:
        return False
    if inspect.iscoroutinefunction(obj):
        return True
    if hasattr(obj, "__call__") and inspect.iscoroutinefunction(obj.__call__):
        return True
    if hasattr(obj, "_is_async") and getattr(obj, "_is_async"):
        return True
    return False


# ── SEQUENTIAL ─────────────────────────────────────────────────────────────────

class SEQUENTIAL:
    """
    Run multiple pre-iteration hooks one after another.

    Supports both sync and async callables. If any hook is async the whole
    chain becomes async and must be awaited.

    Example
    -------
    ::

        from autourgos_preiteration import SEQUENTIAL, PreIterationMiddleware

        def capture_screen(iteration: int) -> None:
            take_screenshot(f"step_{iteration}.png")

        def log_step(iteration: int) -> None:
            print(f"Iteration {iteration} starting")

        middleware = PreIterationMiddleware(
            callback=SEQUENTIAL[capture_screen, log_step]
        )
    """

    def __init__(self, *funcs: Callable[[int], Any]) -> None:
        self.funcs     = [f for f in funcs if f is not None]
        self._is_async = any(is_async_callable(f) for f in self.funcs)

    def __class_getitem__(cls, item: Any) -> "SEQUENTIAL":
        if not isinstance(item, tuple):
            item = (item,)
        return cls(*item)

    def __call__(self, iteration: int) -> Any:
        if self._is_async:
            return self._run_async(iteration)
        for func in self.funcs:
            func(iteration)
        return None

    async def _run_async(self, iteration: int) -> None:
        for func in self.funcs:
            if is_async_callable(func):
                await func(iteration)
            else:
                res = func(iteration)
                if inspect.iscoroutine(res):
                    await res


# ── PARALLEL ───────────────────────────────────────────────────────────────────

class PARALLEL:
    """
    Run multiple pre-iteration hooks at the same time.

    Sync hooks run in a ``ThreadPoolExecutor``; async hooks run as
    ``asyncio`` tasks. Results (and errors) are gathered before the
    agent continues.

    Example
    -------
    ::

        from autourgos_preiteration import PARALLEL, PreIterationMiddleware

        middleware = PreIterationMiddleware(
            callback=PARALLEL[capture_screen, refresh_cache, ping_health_check]
        )
    """

    def __init__(self, *funcs: Callable[[int], Any]) -> None:
        self.funcs     = [f for f in funcs if f is not None]
        self._is_async = any(is_async_callable(f) for f in self.funcs)

    def __class_getitem__(cls, item: Any) -> "PARALLEL":
        if not isinstance(item, tuple):
            item = (item,)
        return cls(*item)

    def __call__(self, iteration: int) -> Any:
        if self._is_async:
            return self._run_async(iteration)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, len(self.funcs))
        ) as executor:
            futures = [executor.submit(func, iteration) for func in self.funcs]
            concurrent.futures.wait(futures)
            for fut in futures:
                fut.result()  # re-raises any exceptions
        return None

    async def _run_async(self, iteration: int) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        tasks = []
        for func in self.funcs:
            if is_async_callable(func):
                tasks.append(asyncio.ensure_future(func(iteration), loop=loop))
            else:
                tasks.append(loop.run_in_executor(None, func, iteration))
        if tasks:
            await asyncio.gather(*tasks)


# ── image helpers ──────────────────────────────────────────────────────────────

_IMAGE_QUALITY_TIERS: Dict[str, Tuple] = {
    "low":    (512,  60,   "low"),
    "medium": (768,  70,   "auto"),
    "high":   (None, None, "high"),
    "auto":   (None, None, "auto"),
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# (source_path, mtime, quality_key) -> preprocessed_path
_image_cache: Dict[Tuple, str] = {}


def _is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _IMAGE_EXTENSIONS


def _detail_for(image_quality: Union[str, int]) -> Optional[str]:
    if isinstance(image_quality, int):
        return "low" if image_quality <= 512 else "auto"
    tier = _IMAGE_QUALITY_TIERS.get(str(image_quality).lower())
    return tier[2] if tier else "auto"


def _preprocess_image(
    path: str,
    image_quality: Union[str, int],
    logger: logging.Logger,
) -> str:
    """Resize and re-encode an image based on image_quality. Results are cached."""
    quality_key = str(image_quality)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return path

    cache_key = (path, mtime, quality_key)
    if cache_key in _image_cache:
        cached = _image_cache[cache_key]
        if os.path.exists(cached):
            return cached

    if isinstance(image_quality, int):
        jpeg_quality = max(1, min(100, image_quality))
        max_dim      = 512 if image_quality <= 512 else None
    else:
        tier = _IMAGE_QUALITY_TIERS.get(
            str(image_quality).lower(), _IMAGE_QUALITY_TIERS["auto"]
        )
        max_dim, jpeg_quality, _ = tier

    if max_dim is None and jpeg_quality is None:
        return path

    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning(
            "Pillow is not installed — image resize/recompress skipped. "
            "Install with: pip install 'autourgos-preiteration[images]'. "
            "The image_detail hint is still applied for OpenAI token savings."
        )
        return path

    try:
        img = Image.open(path).convert("RGB")
        if max_dim is not None:
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        tmp = tempfile.NamedTemporaryFile(
            suffix=".jpg", prefix="autourgos_img_", delete=False
        )
        tmp.close()
        img.save(tmp.name, format="JPEG", quality=jpeg_quality, optimize=True)
        _image_cache[cache_key] = tmp.name
        return tmp.name
    except Exception as exc:
        logger.warning(
            f"Image preprocessing failed for {path!r}: {exc}. Using original."
        )
        return path


# ── PreIterationMiddleware ─────────────────────────────────────────────────────

class PreIterationMiddleware(CallbackHandler):
    """
    Middleware that executes a callback and/or injects files before each
    agent iteration.

    Use this to:

    * Take a screenshot before every iteration and feed it to the LLM.
    * Refresh a live data feed, clear a cache, or ping a health endpoint.
    * Run any custom logic (sync or async) at the start of each loop.

    Parameters
    ----------
    callback : callable, optional
        Sync or async ``callable(iteration: int)``. Wrap multiple callables
        with :class:`SEQUENTIAL` or :class:`PARALLEL`.
    files : str, list of str, or callable(iteration) -> str | list, optional
        File path(s) to inject into the LLM at every iteration. Pass a
        callable to generate paths dynamically (e.g. a screenshot that
        changes every iteration).
    image_quality : str or int
        Controls screenshot token cost. Options:

        * ``"auto"`` (default) — no change, backward-compatible.
        * ``"high"`` — forces ``detail="high"``, no resize.
        * ``"medium"`` — downscales to ≤768 px, JPEG q70, ``detail="auto"``.
        * ``"low"`` — downscales to ≤512 px, JPEG q60, ``detail="low"`` (~85 tokens flat).
        * ``int`` 1–100 — JPEG quality; ``detail="low"`` when ≤512 else ``"auto"``.

        Pillow is required for resize: ``pip install 'autourgos-preiteration[images]'``.

    Example
    -------
    ::

        from autourgos_preiteration import PreIterationMiddleware, SEQUENTIAL

        SCREENSHOT = "/tmp/screen.png"

        def capture(iteration: int) -> None:
            take_screenshot(SCREENSHOT)

        middleware = PreIterationMiddleware(
            callback=capture,
            files=SCREENSHOT,
            image_quality="low",
        )
        agent = ReactAgent(llm=my_llm, middleware=[middleware])
    """

    def __init__(
        self,
        callback: Optional[Callable[[int], Union[None, Awaitable[None]]]] = None,
        files: Optional[
            Union[str, List[str], Callable[[int], Optional[Union[str, List[str]]]]]
        ] = None,
        image_quality: Union[str, int] = "auto",
    ) -> None:
        if isinstance(image_quality, int):
            if not (1 <= image_quality <= 100):
                raise ValueError("image_quality as int must be between 1 and 100.")
        elif str(image_quality).lower() not in _IMAGE_QUALITY_TIERS:
            raise ValueError(
                f"image_quality must be one of {list(_IMAGE_QUALITY_TIERS)} or int 1-100, "
                f"got {image_quality!r}."
            )
        self.callback      = callback
        self._files        = files
        self.image_quality = image_quality
        self._current_kwargs: Dict[str, Any] = {}
        self.logger = logging.getLogger("autourgos.preiteration")

    def on_iteration_start(self, iteration: int, agent: Any = None, **kwargs: Any) -> None:
        # run callback
        if self.callback:
            try:
                res = self.callback(iteration)
                if inspect.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.run_coroutine_threadsafe(res, loop).result()
                    except RuntimeError:
                        asyncio.run(res)
            except Exception as exc:
                self.logger.error(
                    f"Error in pre-iteration callback at iteration {iteration}: {exc}"
                )
                raise

        # resolve files
        self._current_kwargs = {}
        if self._files is not None:
            resolved = self._files(iteration) if callable(self._files) else self._files
            if resolved:
                raw: List[str] = []
                if isinstance(resolved, list):
                    raw = [f for f in resolved if f and os.path.exists(f)]
                elif isinstance(resolved, str) and os.path.exists(resolved):
                    raw = [resolved]

                if raw:
                    processed = [
                        _preprocess_image(f, self.image_quality, self.logger)
                        if _is_image(f) else f
                        for f in raw
                    ]
                    self._current_kwargs["files"] = processed
                    detail = _detail_for(self.image_quality)
                    if detail is not None:
                        self._current_kwargs["image_detail"] = detail

    def get_injection_kwargs(self) -> Dict[str, Any]:
        """Return file-injection kwargs to pass to the LLM call."""
        return dict(self._current_kwargs)
