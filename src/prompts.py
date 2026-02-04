"""Centralized prompts for Sliding Puzzle Task."""

# Single prompt with dynamic move count and constraints
# This matches the VMEvalKit implementation
PROMPTS = [
    "Complete this sliding puzzle. The goal is to arrange the numbered tiles in sequential order "
    "(filling each row from left to right, with rows from top to bottom), "
    "with the blank space at the bottom-right corner.\n\n"
    "Rules: Only tiles adjacent to the blank space can be moved. Slide one tile per move into the blank space.\n\n"
    "Complete in exactly {num_moves} move{plural}.\n\n"
    "Do not make extra moves. Keep the camera view fixed and maintain the grid structure unchanged.",
]

DEFAULT_PROMPT_INDEX = 0


def get_prompt(task_type: str = "default", num_moves: int = 1) -> str:
    """
    Get prompt for sliding puzzle task with dynamic move count.
    
    Matches VMEvalKit's prompt format and structure.
    
    Args:
        task_type: Type of task (for compatibility, not used currently)
        num_moves: Number of moves needed to solve
        
    Returns:
        Formatted prompt string
    """
    template = PROMPTS[DEFAULT_PROMPT_INDEX]
    plural = "s" if num_moves > 1 else ""
    return template.format(num_moves=num_moves, plural=plural)


def get_all_prompts(task_type: str = "default") -> list[str]:
    """Get all prompts for a given task type."""
    return PROMPTS
