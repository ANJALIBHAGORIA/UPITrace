class AIProviderUnavailable(Exception):
    """Raised when the configured AI provider cannot be used (missing
    credentials, missing SDK, missing project config, or a call-time auth
    failure). The orchestrator catches this and falls back to the
    deterministic reconciliation result — it never fabricates a response in
    place of a real one."""
