"""
Tests for autourgos_preiteration.middleware — regression + temp-file cleanup.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from autourgos_agent.testing import make_test_agent

from autourgos_preiteration import middleware as mw_module
from autourgos_preiteration.middleware import PreIterationMiddleware


class FakeAgent:
    name = "TestAgent"

    def __init__(self, logger=None):
        if logger is not None:
            self.logger = logger


@pytest.fixture(autouse=True)
def clear_image_cache():
    """Each test starts with a clean shared image cache."""
    mw_module._image_cache.clear()
    yield
    mw_module._image_cache.clear()


def _make_image(path: str, size=(1000, 1000)) -> None:
    img = Image.new("RGB", size, color=(120, 45, 200))
    img.save(path, format="PNG")


def test_normal_image_injection_still_works(tmp_path):
    """Regression: files get resolved, preprocessed, and injected as kwargs."""
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    middleware.on_iteration_start(1, agent=FakeAgent())

    kwargs = middleware.get_injection_kwargs()
    assert "files" in kwargs
    assert len(kwargs["files"]) == 1
    processed_path = kwargs["files"][0]
    assert os.path.exists(processed_path)
    assert processed_path != img_path  # was compressed into a new temp file
    assert kwargs.get("image_detail") == "low"


def test_temp_files_cleaned_up_after_agent_end(tmp_path):
    """Temp files created during a run should be removed once on_agent_end fires,
    provided they are no longer referenced by the shared cache (e.g. the image
    changed mid-run, evicting the earlier temp file from the cache)."""
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    agent = FakeAgent()

    middleware.on_iteration_start(1, agent=agent)
    first_processed = middleware.get_injection_kwargs()["files"][0]
    assert os.path.exists(first_processed)

    # Simulate the image changing mid-run (new mtime => cache miss). The
    # cache is keyed by (path, quality) without mtime, so _preprocess_image
    # itself evicts and deletes the stale (path, quality) entry's temp file
    # as soon as the new one is produced -- no manual eviction needed here.
    os.utime(img_path, None)
    _make_image(img_path, size=(50, 50))
    os.utime(img_path, (os.path.getatime(img_path), os.path.getmtime(img_path) + 5))

    middleware.on_iteration_start(2, agent=agent)
    second_processed = middleware.get_injection_kwargs()["files"][0]

    assert first_processed != second_processed
    # the stale entry was deleted immediately on mtime-change, not left to
    # accumulate until on_agent_end's cleanup pass.
    assert not os.path.exists(first_processed)

    middleware.on_agent_end("done", agent=agent)

    assert not os.path.exists(first_processed)
    # the currently cached temp file must survive cleanup (still referenced)
    assert os.path.exists(second_processed)


def test_temp_files_cleaned_up_after_agent_error(tmp_path):
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    agent = FakeAgent()
    middleware.on_iteration_start(1, agent=agent)
    processed = middleware.get_injection_kwargs()["files"][0]
    assert os.path.exists(processed)

    # Manually evict from cache to simulate it no longer being referenced.
    mw_module._image_cache.clear()

    middleware.on_agent_error(RuntimeError("boom"), agent=agent)
    assert not os.path.exists(processed)


def test_image_cache_avoids_reprocessing_same_image(tmp_path, monkeypatch):
    """Repeated calls for the same unchanged image should hit the cache and
    avoid calling Pillow's Image.open again."""
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    call_count = {"n": 0}
    original_open = Image.open

    def counting_open(*args, **kwargs):
        call_count["n"] += 1
        return original_open(*args, **kwargs)

    monkeypatch.setattr(Image, "open", counting_open)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    agent = FakeAgent()

    middleware.on_iteration_start(1, agent=agent)
    first_processed = middleware.get_injection_kwargs()["files"][0]

    middleware.on_iteration_start(2, agent=agent)
    second_processed = middleware.get_injection_kwargs()["files"][0]

    assert first_processed == second_processed
    assert call_count["n"] == 1

    middleware.on_agent_end("done", agent=agent)
    # still cached -> survives cleanup
    assert os.path.exists(first_processed)


def test_narrates_via_agent_logger_middleware_when_files_injected(tmp_path):
    """When files are actually resolved and injected for an iteration, the
    middleware should call agent.logger.middleware(...) with source
    'PreIteration' and a message describing the injection."""
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    fake_logger = MagicMock()
    agent = FakeAgent(logger=fake_logger)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    middleware.on_iteration_start(2, agent=agent)

    assert fake_logger.middleware.called
    args, _ = fake_logger.middleware.call_args
    assert args[0] == "PreIteration"
    assert "Injected 1 file(s)" in args[1]
    assert "iteration 2" in args[1]


def test_no_narration_when_no_files_injected():
    """If no files were resolved/injected for this iteration, don't narrate."""
    fake_logger = MagicMock()
    agent = FakeAgent(logger=fake_logger)

    middleware = PreIterationMiddleware()  # no files configured
    middleware.on_iteration_start(1, agent=agent)

    assert not fake_logger.middleware.called


def test_no_crash_when_agent_has_no_logger_attribute(tmp_path):
    """Defensive: agent objects without a .logger attribute must not crash
    the middleware."""
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    agent = FakeAgent()  # no logger attribute set
    assert not hasattr(agent, "logger")

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    middleware.on_iteration_start(1, agent=agent)

    kwargs = middleware.get_injection_kwargs()
    assert "files" in kwargs


# -- on_before_iteration reaches the real LLM call (real Agent) ----------
#
# Before this release, get_injection_kwargs() was computed but nothing ever
# called it — react-agent only accepted extra_kwargs once at invoke() time.
# These tests verify the new on_before_iteration hook actually plumbs the
# resolved files/image_detail kwargs into the real per-iteration LLM call.

def test_on_before_iteration_returns_the_resolved_injection_kwargs(tmp_path):
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    agent = FakeAgent()

    middleware.on_iteration_start(1, agent=agent)
    result = middleware.on_before_iteration(1, agent=agent)

    assert result is not None
    assert "files" in result
    assert result.get("image_detail") == "low"
    # must match exactly what get_injection_kwargs() reports
    assert result == middleware.get_injection_kwargs()


def test_on_before_iteration_returns_none_when_no_files_resolved():
    middleware = PreIterationMiddleware()  # no files configured
    agent = FakeAgent()

    middleware.on_iteration_start(1, agent=agent)
    result = middleware.on_before_iteration(1, agent=agent)

    assert result is None


def test_real_agent_llm_invoke_actually_receives_injected_kwargs(tmp_path):
    """
    End-to-end against a real Agent (make_test_agent): the scripted
    fake LLM records the kwargs it was called with for each iteration. This
    asserts that the files/image_detail kwargs PreIterationMiddleware
    resolves via on_iteration_start actually reach the real
    llm.invoke() call for that same iteration, via the new
    on_before_iteration hook.
    """
    img_path = str(tmp_path / "shot.png")
    _make_image(img_path)

    middleware = PreIterationMiddleware(files=img_path, image_quality="low")
    responses = [
        json.dumps({"thought": None, "actions": [], "final_answer": "ok"}),
    ]
    agent = make_test_agent(responses=responses, middleware=[middleware])

    result = agent.invoke("look at this image")

    assert result == "ok"
    assert len(agent.llm.calls) == 1
    received_kwargs = agent.llm.calls[0]["kwargs"]
    assert "files" in received_kwargs
    assert len(received_kwargs["files"]) == 1
    assert os.path.exists(received_kwargs["files"][0])
    assert received_kwargs.get("image_detail") == "low"
