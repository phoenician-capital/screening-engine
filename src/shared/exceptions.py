"""Custom exceptions for screening pipeline."""


class ScoringError(Exception):
    """Non-fatal scoring error (one company failed, continue)."""
    pass


class PipelineError(Exception):
    """Fatal pipeline error (stop screening)."""
    pass


class RetryableError(ScoringError):
    """Error that should trigger a retry."""
    pass
