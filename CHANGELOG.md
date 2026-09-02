# Changelog

## [3.0.7] - 2026-09-01

- Dependency: raised the `autourgos-agent` floor from `>=2.0.2` to
  `>=3.1.0`. `autourgos-agent` 3.1.0 added sync-hook thread offloading in
  `CallbackManager` under `ainvoke()` (a sync `on_iteration_start`/etc.
  handler now runs off the event-loop thread instead of inline) -- below
  that version, a blocking call inside this middleware's hooks would stall
  every other concurrent `ainvoke()` run sharing that thread. The old
  floor allowed resolving against a pre-3.1.0 install that lacks this fix.
  No code changes here.

## [3.0.6] - 2026-09-01

- Metadata: added `maintainers` (Sonia, Vishwanil Suman) to `pyproject.toml`,
  and linked the README's existing Sonia contributor badge to her GitHub
  profile (https://github.com/dahiyasonia). No code changes.

## [3.0.5] - 2026-09-01

- Fixed: the shared module-level image preprocessing cache had no size
  bound. A dynamic `files=` callable generating a new source path every
  iteration (a documented pattern, e.g. per-iteration screenshot
  filenames) grew the cache -- and its backing temp files -- without limit
  for the life of the process. Now capped at 256 entries
  (`_IMAGE_CACHE_MAX_ENTRIES`), evicting the least-recently-used entry
  (and deleting its temp file) once exceeded. The documented headline use
  case -- repeatedly processing the same source path -- never grows past
  one entry per (path, quality) and is unaffected.
- Fixed: `_preprocess_image` never closed the `PIL.Image` opened for the
  source file (`Image.open(path).convert("RGB")`), relying on GC. Now
  opened via `with Image.open(path) as src: ...`, closing the source
  handle explicitly once the RGB-converted copy is made.

## [3.0.4] - 2026-09-01

- Cleaned up: `PARALLEL._run_async`'s fallback that created and installed a
  brand new event loop when `asyncio.get_running_loop()` raised was dead
  code -- `_run_async` is a coroutine function whose body only ever executes
  once something is already driving it inside a running loop, so that
  branch could never actually be reached. Simplified to call
  `asyncio.get_running_loop()` directly. No behavior change.

## [3.0.3] - 2026-09-01

- Fixed: an async `callback=` coroutine's result used to be driven via
  `asyncio.get_running_loop()` + `run_coroutine_threadsafe(res, loop).result()`.
  Whenever `get_running_loop()` succeeds, the calling thread IS the loop's
  own thread -- `agent.ainvoke()` calls the sync `on_iteration_start` hook
  directly from the event-loop thread, not from a separate one -- so
  scheduling the coroutine on that same loop and then blocking that thread
  waiting for the loop to run it deadlocked every time this branch was
  reached, not just in some edge case. The coroutine is now driven via a
  helper that runs it on an isolated thread with its own fresh event loop
  whenever a loop is already running on the calling thread, sidestepping
  the deadlock entirely. No change to the no-running-loop case (still
  `asyncio.run(coro)` directly).

## [3.0.2] - 2026-09-01

- Fixed: the `callback=` parameter's `on_iteration_start` handler used to
  re-raise an exception after logging it. `autourgos-agent`'s
  `CallbackManager` catches every exception a hook raises unconditionally,
  so that re-raise could never actually reach or stop the agent run — its
  only real effect was silently skipping file resolution for that
  iteration. Now logs the error and still resolves/injects files, matching
  how every other middleware in this ecosystem treats a hook failure.

## [3.0.0] - 2026-07-27 (unreleased on PyPI until now)

- BREAKING: requires autourgos-agent>=2.0.2 (previously pinned to
  autourgos-react-agent>=1.6.0 before this version ever shipped to PyPI —
  autourgos-react-agent's releases are now fully yanked and this floor
  would have made the package uninstallable from day one).
- Fixed: per-iteration file injection (`files=`/`image_quality=`) was
  silently broken against a real `Agent` — `get_injection_kwargs()`
  was never called by anything, because the agent loop previously only
  accepted `extra_kwargs` once at `invoke()` time. This release implements
  `on_before_iteration` on `PreIterationMiddleware`, using the
  `on_before_iteration` hook so the files/image_detail kwargs resolved by
  `on_iteration_start` are now actually merged into that iteration's real
  LLM call.
- Tests rewritten to run against `make_test_agent()` (a real `Agent`)
  instead of hand-rolled fake agents, and now assert that the LLM's
  `.invoke()` call for an iteration actually received the `files`/
  `image_detail` kwargs that preiteration computed.

## [2.1.1] - 2026-07-27

- Fixed: standardized logger to logging.getLogger(__name__); temp-file cleanup failures during on_agent_end/on_agent_error are now logged at debug level instead of silently swallowed.

## [2.1.0] - 2026-07-27

- Added: narrates its own actions into the host ReactAgent's verbose trace via
  `agent.logger.middleware(...)` when available (see autourgos-react-agent's
  README for the pattern). Purely additive and defensive -- no crash if the
  host agent has no `.logger`, no output when verbose=False, no logging
  previously existed in this package.

## [2.0.0] - 2026-07-27

- BREAKING: this package now depends on autourgos-react-agent>=1.1.0
  (previously zero-dependency). `CallbackHandler` is now re-exported from
  autourgos-react-agent instead of being duplicated locally, to eliminate
  interface drift risk. No public API/behavior change for typical usage —
  `CallbackHandler`'s method signatures and semantics are unchanged.

## [1.0.2] - 2026-07-27

- Fix: Pillow-compressed temp files created by `_preprocess_image` were never
  cleaned up, leaking disk space over the lifetime of a long-running agent.
  `PreIterationMiddleware` now tracks temp files created during each run and
  removes them in new `on_agent_end`/`on_agent_error` hooks, skipping any
  file still referenced by the shared image cache so repeated calls for the
  same unchanged image continue to hit the cache.

## [1.0.1] - 2026-06-17

- Update Documentation
