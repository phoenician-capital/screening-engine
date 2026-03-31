"""Base agent class with common interface for selection and scoring agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentDecision:
    """Standard output format for all agents."""
    passed: bool
    score: float | None = None
    reason: str | None = None
    metadata: dict | None = None


class BaseAgent(ABC):
    """Base class for all selection/scoring agents."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def evaluate(self, **kwargs) -> AgentDecision:
        """Evaluate input and return decision."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}'>"
