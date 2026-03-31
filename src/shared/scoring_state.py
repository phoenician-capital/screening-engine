"""Screening progress and state tracking."""

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class ScreeningProgress:
    """Real-time progress update from coordinator."""

    step: str  # "discovery", "scoring", "retry", "ranking", "complete"
    status: str = "in_progress"  # "starting", "in_progress", "complete", "failed"
    total_companies: int = 0
    companies_scored: int = 0
    failed_companies: int = 0
    current_ticker: Optional[str] = None
    total_ranked: int = 0
    error_message: Optional[str] = None
    elapsed_seconds: float = 0

    def dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def __str__(self):
        return (
            f"[{self.step.upper()}] {self.status} | "
            f"scored={self.companies_scored}/{self.total_companies} | "
            f"failed={self.failed_companies} | "
            f"ticker={self.current_ticker} | {self.elapsed_seconds:.1f}s"
        )
