"""Provider adapters — one per web-LLM target (Claude, ChatGPT, Gemini, Grok).

The provider adapter is the only layer that knows the UI of a particular
LLM web app. Everything else (Backend, Router, Agent) talks to it through
`BaseWebLLMProvider`.
"""
