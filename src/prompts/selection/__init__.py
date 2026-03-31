"""Selection Team prompts."""

from pathlib import Path

def load_selection_prompt(agent_name: str, section: str = "system") -> str:
    """Load a selection agent prompt.

    Args:
        agent_name: 'filter', 'business_model', 'founder', 'growth', 'red_flag'
        section: 'system' or 'user'

    Returns:
        Prompt template string (not yet rendered)
    """
    prompt_dir = Path(__file__).parent
    filename = f"{agent_name}_agent_{section}.j2"

    prompt_path = prompt_dir / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {filename}")

    return prompt_path.read_text()

def load_selection_evaluation() -> str:
    """Load the full selection evaluation template."""
    prompt_dir = Path(__file__).parent
    return (prompt_dir / "selection_evaluation.j2").read_text()
