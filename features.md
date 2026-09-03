# autourgos-preiteration — Features

A middleware for [Autourgos](https://github.com/devxjitin) agents that runs a sync or async callback —
and optionally injects files like screenshots — before every agent iteration, with built-in image
compression to keep vision-LLM costs down. Typical use: computer-use agents that need a fresh screenshot
before each reasoning step.

## Full Feature List

- **Fresh context every iteration** — run any callback (screenshot capture, live price/sensor feed, a
  health ping, iteration logging) right before each LLM call
- **`SEQUENTIAL`/`PARALLEL` combinators** — compose multiple callbacks to run one-after-another or
  concurrently
- **Sync and async callbacks**, both working inside `invoke()` and `ainvoke()`
- **Dynamic file injection** — `files` can be a static path, a list, or a callable that generates a fresh
  path per iteration (e.g. `screen_{iteration}.png`)
- **Built-in image compression** (via optional Pillow) — five tunable levels from a flat ~85 tokens
  (`"low"`, 512px/quality 60) up to `"auto"` (no resize, provider-default detail); also accepts an int
  1-100 for a custom JPEG quality; without Pillow the `image_detail` hint still applies but no
  resize/recompress happens
- **Verbose tracing** — narrates its own injections into the agent's `verbose=True` trace
  (`[PreIteration] Injected N file(s) before iteration K.`)
- **Zero required dependencies**, works with any Autourgos agent (sync/async)

---

## Competitor Comparison

This is a narrow scheduling+compression primitive for one specific need — inject fresh
files/context before every agent step — rather than a general context-management system. The closest
real comparisons are the context/image-handling pieces of larger agent frameworks, plus general image
compression practice for vision LLM calls.

| Capability | **autourgos-preiteration** | [LangChain agent middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) | [LangChain `SummarizationMiddleware`](https://www.langchain.com/blog/context-management-for-deepagents) | Manual custom loop code |
|---|---|---|---|---|
| Scope | Single-purpose: run-callback-before-each-iteration | General before/after hooks around messages, tool calls, model calls | Context-window compression specifically (text summarization) | Whatever you write |
| Per-iteration fresh file/screenshot injection | Yes, first-class (`files=`, static or dynamic callable) | Not a built-in primitive — you'd write a custom middleware | No — focused on text summarization, not media injection | DIY |
| Built-in image compression for cost control | Yes, tunable presets tied to token-cost tiers (`"low"`/`"medium"`/`"high"`/`"auto"`/int) | No built-in equivalent | Explicitly does **not** resize/downsample image payloads — recommends storing media externally and passing references instead | DIY |
| Sequential/parallel multi-callback composition | Yes, `SEQUENTIAL`/`PARALLEL` combinators | Yes — multiple middleware can be chained, order matters | N/A (single-purpose middleware) | DIY |
| Async support | Yes, native | Yes | Yes | DIY |
| Framework coupling | Any Autourgos agent | LangChain agents only | LangChain agents only | None |
| Handles old/stale image messages in long-running context | No — its job is pre-iteration injection, not history pruning | Depends on middleware chain | Yes — this is its specialty (summarizes old multimodal messages to text) | DIY |
| Pricing | Free, open source | Free, open source | Free, open source | Free (your own code) |

### How to read this

- autourgos-preiteration and LangChain's middleware ecosystem overlap only partially: LangChain's
  `SummarizationMiddleware` solves the "context window is getting too big, compress old messages"
  problem and explicitly does not compress images — it says to keep images out-of-band via file/URL
  references instead. autourgos-preiteration solves the adjacent-but-different "give me fresh,
  cost-controlled image context on every single iteration" problem, with actual pixel-level
  resize/recompress built in.
- If your problem is a long-running agent's context window growing too large from old messages,
  LangChain's summarization middleware is the more directly applicable tool. If your problem is a
  computer-use-style agent that needs a cheap fresh screenshot (or other file) before every step,
  autourgos-preiteration's compression presets map more directly to that need.
- General LangChain agent middleware gives you the hook points (before/after model call) but no
  ready-made image-compression or dynamic-file-injection logic — you'd build both from scratch, which
  is exactly what this library packages up.
- This is a lightweight utility, not a replacement for a full context-management strategy; teams running
  very long agent loops will likely want both a summarization/pruning layer (for old messages) and this
  kind of pre-iteration injector (for fresh per-step context).

Sources:
- [Prebuilt middleware - Docs by LangChain](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [Context Management for Deep Agents](https://www.langchain.com/blog/context-management-for-deepagents)
- [Deep Agents: Clarify Multimodal (Image) Context Management and Compression - LangChain Forum](https://forum.langchain.com/t/deep-agents-clarify-multimodal-image-context-management/3485)
- [How LangChain Middleware Makes AI Agents More Reliable | Medium](https://medium.com/@sjha979/building-smarter-ai-agents-using-langchain-middleware-f8a3e3b75cd7)
- [Automatic Context Compression in LLM Agents | Medium](https://medium.com/the-ai-forum/automatic-context-compression-in-llm-agents-why-agents-need-to-forget-and-how-to-help-them-do-it-43bff14c341d)
