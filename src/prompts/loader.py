"""
Jinja2-based prompt loader.

All prompts live as .j2 files under src/prompts/<domain>/.
This loader renders them with variables at call time, keeping
prompt text fully separate from business logic.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


class PromptLoader:
    """
    Render a Jinja2 prompt template.

    Usage:
        loader = PromptLoader()
        text = loader.render("extraction/parse_financials.j2", text=raw_text)
    """

    def __init__(self) -> None:
        self.env = _get_env()

    def render(self, template_path: str, **kwargs: Any) -> str:
        """Render a .j2 template with the given variables."""
        tpl = self.env.get_template(template_path)
        return tpl.render(**kwargs)


# Module-level convenience function
_loader = PromptLoader()


def load_prompt(template_path: str, **kwargs: Any) -> str:
    """Render a prompt template. Shorthand for PromptLoader().render(...)."""
    return _loader.render(template_path, **kwargs)
