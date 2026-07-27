# Changelog

## [3.0.0] - 2026-07-27

- BREAKING: requires autourgos-react-agent>=1.6.0.
- Fixed: per-iteration file injection (`files=`/`image_quality=`) was
  silently broken against a real `ReactAgent` — `get_injection_kwargs()`
  was never called by anything, because react-agent previously only
  accepted `extra_kwargs` once at `invoke()` time. This release implements
  `on_before_iteration` on `PreIterationMiddleware`, using the new
  react-agent 1.6.0 hook so the files/image_detail kwargs resolved by
  `on_iteration_start` are now actually merged into that iteration's real
  LLM call.
- Tests rewritten to run against `make_test_agent()` (a real `ReactAgent`)
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
