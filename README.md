# autourgos-preiteration

Pre-iteration middleware for [Autourgos](https://github.com/devxjitin) agents.

Run any sync or async callback — and inject files like screenshots — before every agent iteration. Built-in image compression keeps vision LLM costs low.

---

## Why use this?

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

Zero required dependencies. Works with any Autourgos agent.

---

## Quick Start

```python
from autourgos_preiteration import PreIterationMiddleware
from autourgos_react_agent import ReactAgent

SCREENSHOT = "/tmp/screen.png"

def capture(iteration: int) -> None:
    take_screenshot(SCREENSHOT)  # your screenshot function

middleware = PreIterationMiddleware(
    callback=capture,
    files=SCREENSHOT,
    image_quality="low",  # ~85 tokens flat — great for computer-use agents
)

agent = ReactAgent(llm=my_llm, middleware=[middleware])
result = agent.invoke("Open the browser and search for Python 3.13 release notes")
print(result)
```

When used with a verbose `ReactAgent` (`verbose=True`), `PreIterationMiddleware` also narrates its own actions into the agent's trace, right alongside the Thought/Action/Observation lines, e.g.:

```
[PreIteration] Injected 1 file(s) before iteration 2.
```

---

## Run multiple callbacks

### SEQUENTIAL — one after another

```python
from autourgos_preiteration import PreIterationMiddleware, SEQUENTIAL

def capture_screen(iteration: int) -> None:
    take_screenshot("/tmp/screen.png")

def log_step(iteration: int) -> None:
    print(f"Starting iteration {iteration}")

middleware = PreIterationMiddleware(
    callback=SEQUENTIAL[capture_screen, log_step]
)
```

### PARALLEL — all at the same time

```python
from autourgos_preiteration import PreIterationMiddleware, PARALLEL

def capture_screen(iteration: int) -> None:
    take_screenshot("/tmp/screen.png")

def refresh_cache(iteration: int) -> None:
    cache.clear()

def ping_health(iteration: int) -> None:
    requests.get("https://api.example.com/health")

middleware = PreIterationMiddleware(
    callback=PARALLEL[capture_screen, refresh_cache, ping_health]
)
```

---

## Async callbacks

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

## Dynamic file injection

Pass a callable for `files` to generate paths per iteration:

```python
def get_screenshot_path(iteration: int) -> str:
    path = f"/tmp/screen_{iteration}.png"
    take_screenshot(path)
    return path

middleware = PreIterationMiddleware(files=get_screenshot_path, image_quality="medium")
```

---

## Image quality

Control how much each screenshot costs in LLM tokens:

| Value | Max size | JPEG quality | OpenAI detail | Approx tokens |
|---|---|---|---|---|
| `"auto"` (default) | No resize | No change | `"auto"` | Varies |
| `"high"` | No resize | No change | `"high"` | ~1000+ |
| `"medium"` | 768 px | 70 | `"auto"` | ~300–500 |
| `"low"` | 512 px | 60 | `"low"` | ~85 (flat) |
| int 1–100 | 512 px if ≤512 | That value | `"low"` / `"auto"` | Varies |

Resize requires Pillow: `pip install 'autourgos-preiteration[images]'`

If Pillow is not installed, the `image_detail` hint is still applied (token savings from the detail flag alone), but no resize/recompress happens.

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `callback` | callable or None | `None` | Sync/async function `(iteration: int)`. Wrap with `SEQUENTIAL` or `PARALLEL` for multiple hooks. |
| `files` | str, list, callable, or None | `None` | File path(s) to inject into LLM. Callable receives iteration number. |
| `image_quality` | str or int | `"auto"` | Image compression level. See table above. |

---

## Combine with other middleware

```python
from autourgos_preiteration import PreIterationMiddleware
from autourgos_history import AgentHistoryMiddleware
from autourgos_summarizer import AutoSummarizeMiddleware

middleware = [
    PreIterationMiddleware(callback=capture, files="/tmp/screen.png", image_quality="low"),
    AutoSummarizeMiddleware(summarize_every=5),
    AgentHistoryMiddleware(),
]
agent = ReactAgent(llm=my_llm, middleware=middleware)
```

---

## Requirements

- Python 3.9+
- Pillow (optional) — for image resize: `pip install 'autourgos-preiteration[images]'`

---

## Links

- PyPI: https://pypi.org/project/autourgos-preiteration/
- GitHub: https://github.com/devxjitin/autourgos-preiteration
- Issues: https://github.com/devxjitin/autourgos-preiteration/issues

---

## License

MIT — see [LICENSE](LICENSE)
