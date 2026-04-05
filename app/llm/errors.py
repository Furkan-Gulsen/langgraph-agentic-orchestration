"""LLM-related errors."""


class LLMError(Exception):
    """Base class for provider failures."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMTimeout(LLMError):
    """Request exceeded configured timeout."""

    def __init__(self, message: str = "LLM request timed out") -> None:
        super().__init__(message, retryable=True)


class LLMResponseError(LLMError):
    """Invalid or empty response from the model."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)
