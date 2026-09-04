# autourgos-preiteration

[![Framework: Autourgos](https://img.shields.io/badge/Framework-Autourgos-orange.svg)](https://github.com/devxjitin)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://pypi.org/project/autourgos-preiteration/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/devxjitin/autourgos-preiteration/blob/main/LICENSE)
[![Author](https://img.shields.io/badge/Author-Jitin%20Kumar%20Sengar-blue.svg)](https://github.com/devxjitin)
[![Contributor](https://img.shields.io/badge/Contributor-Sonia-blueviolet.svg)](https://github.com/dahiyasonia)
[![Contributor](https://img.shields.io/badge/Contributor-Vishwanil%20Suman-blueviolet.svg)]()

Pre-iteration middleware for [Autourgos](https://github.com/devxjitin) agents. Run any sync or async callback
— and inject files like screenshots — before every agent iteration. Built-in image compression keeps vision
LLM costs low.

```python
from autourgos_preiteration import PreIterationMiddleware
from autourgos_agent import Agent

middleware = PreIterationMiddleware(callback=capture, files="/tmp/screen.png", image_quality="low")
agent = Agent(llm=my_llm, middleware=[middleware])
result = agent.invoke("Open the browser and search for Python 3.13 release notes")
```

---

## Features

- **Fresh context every iteration** — screenshots, live data, health pings, whatever your callback produces
- **`SEQUENTIAL`/`PARALLEL` combinators** for running multiple callbacks
- **Sync and async callbacks**, both work inside `invoke()` and `ainvoke()`
- **Dynamic file injection** — pass a callable for `files` to generate a fresh path per iteration
- **Built-in image compression** (via optional Pillow) — from a flat ~85 tokens (`"low"`) to no resize
  (`"auto"`)
- **Concurrency-safe** — per-run resolved files/temp-file state isolated via `contextvars.ContextVar`
  (`autourgos-core`'s `RunScopedState`), correct for both concurrent threads and concurrent `asyncio`
  tasks sharing one thread
- Zero required dependencies; works with any Autourgos agent

---

## Table of Contents

- [Why Use This?](#why-use-this)
- [Install](#install)
- [Quick Start](#quick-start)
- [Run Multiple Callbacks](#run-multiple-callbacks)
- [Async Callbacks](#async-callbacks)
- [Dynamic File Injection](#dynamic-file-injection)
- [Image Quality](#image-quality)
- [Parameters](#parameters)
- [License](#license)

---

## Why Use This?

Some agent tasks need fresh context every iteration:

- **Computer-use agents** — take a screenshot before each step so the LLM sees the current screen state
- **Live data agents** — refresh a price feed, sensor reading, or API response before each reasoning step
- **Monitoring agents** — ping a health endpoint or log iteration metrics before the LLM call

`PreIterationMiddleware` handles all of this cleanly, with zero boilerplate inside your agent.

---

## Install

```bash
pip install autourgos-preiteration
```

For image resize/compression support (Pillow):

```bash
pip install 'autourgos-preiteration[images]'
```

---

## Quick Start

```python
from autourgos_preiteration import PreIterationMiddleware
from autourgos_agent import Agent

SCREENSHOT = "/tmp/screen.png"

def capture(iteration: int) -> None:
    take_screenshot(SCREENSHOT)  # your screenshot function

middleware = PreIterationMiddleware(
    callback=capture,
    files=SCREENSHOT,
    image_quality="low",  # ~85 tokens flat — great for computer-use agents
)

agent = Agent(llm=my_llm, middleware=[middleware])
result = agent.invoke("Open the browser and search for Python 3.13 release notes")
print(result)
```

With `Agent(verbose=True)`, this middleware also narrates its own actions into the agent's trace:

```
[PreIteration] Injected 1 file(s) before iteration 2.
```

---

## Run Multiple Callbacks

### SEQUENTIAL — one after another

```python
from autourgos_preiteration import PreIterationMiddleware, SEQUENTIAL

def capture_screen(iteration: int) -> None:
    take_screenshot("/tmp/screen.png")

def log_step(iteration: int) -> None:
    print(f"Starting iteration {iteration}")

middleware = PreIterationMiddleware(callback=SEQUENTIAL[capture_screen, log_step])
```

### PARALLEL — all at the same time

```python
from autourgos_preiteration import PreIterationMiddleware, PARALLEL

def refresh_cache(iteration: int) -> None:
    cache.clear()

def ping_health(iteration: int) -> None:
    requests.get("https://api.example.com/health")

middleware = PreIterationMiddleware(callback=PARALLEL[capture_screen, refresh_cache, ping_health])
```

---

## Async Callbacks

```python
import asyncio
from autourgos_preiteration import PreIterationMiddleware

async def async_capture(iteration: int) -> None:
    await asyncio.sleep(0)  # non-blocking
    take_screenshot("/tmp/screen.png")

middleware = PreIterationMiddleware(callback=async_capture)
```

Works inside both `agent.invoke()` (sync) and `agent.ainvoke()` (async).

---

## Dynamic File Injection

Pass a callable for `files` to generate paths per iteration:

```python
def get_screenshot_path(iteration: int) -> str:
    path = f"/tmp/screen_{iteration}.png"
    take_screenshot(path)
    return path

middleware = PreIterationMiddleware(files=get_screenshot_path, image_quality="medium")
```

---

## Image Quality

| Value | Max size | JPEG quality | OpenAI detail | Approx tokens |
|---|---|---|---|---|
| `"auto"` (default) | No resize | No change | `"auto"` | Varies |
| `"high"` | No resize | No change | `"high"` | ~1000+ |
| `"medium"` | 768 px | 70 | `"auto"` | ~300–500 |
| `"low"` | 512 px | 60 | `"low"` | ~85 (flat) |
| int 1–100 | 512 px if ≤512 | That value | `"low"` / `"auto"` | Varies |

Resize requires Pillow: `pip install 'autourgos-preiteration[images]'`. Without Pillow, the `image_detail`
hint is still applied, but no resize/recompress happens.

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `callback` | callable or None | `None` | Sync/async function `(iteration: int)`. Wrap with `SEQUENTIAL` or `PARALLEL` for multiple hooks. |
| `files` | str, list, callable, or None | `None` | File path(s) to inject into LLM. Callable receives iteration number. |
| `image_quality` | str or int | `"auto"` | Image compression level. See table above. |

---

## License

Apache License 2.0, Copyright (c) 2026 Jitin Kumar Sengar
