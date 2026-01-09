"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           YOUR TASK CONFIGURATION                             ║
║                                                                               ║
║  CUSTOMIZE THIS FILE to define your task-specific settings.                   ║
║  Inherits common settings from core.GenerationConfig                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from typing import Optional
from pydantic import Field
from core import GenerationConfig


class TaskConfig(GenerationConfig):
    """
    Your task-specific configuration.
    
    CUSTOMIZE THIS CLASS to add your task's hyperparameters.
    
    Inherited from GenerationConfig:
        - num_samples: int          # Number of samples to generate
        - domain: str               # Task domain name
        - difficulty: Optional[str] # Difficulty level
        - random_seed: Optional[int] # For reproducibility
        - output_dir: Path          # Where to save outputs
        - image_size: tuple[int, int] # Image dimensions
    """
    
    # ══════════════════════════════════════════════════════════════════════════
    #  OVERRIDE DEFAULTS
    # ══════════════════════════════════════════════════════════════════════════
    
    domain: str = Field(default="sliding_puzzle")
    image_size: tuple[int, int] = Field(default=(400, 400))
    
    # ══════════════════════════════════════════════════════════════════════════
    #  VIDEO SETTINGS
    # ══════════════════════════════════════════════════════════════════════════
    
    generate_videos: bool = Field(
        default=True,
        description="Whether to generate ground truth videos"
    )
    
    video_fps: int = Field(
        default=10,
        description="Video frame rate"
    )
    
    # ══════════════════════════════════════════════════════════════════════════
    #  SLIDING PUZZLE SETTINGS
    # ══════════════════════════════════════════════════════════════════════════
    
    puzzle_size: int = Field(
        default=3,
        description="Puzzle size (3, 4, or 5 for 3×3, 4×4, 5×5). Used when difficulty_distribution is None."
    )
    
    num_moves: int = Field(
        default=5,
        description="Number of moves from complete state (1-20). Used when difficulty_distribution is None."
    )
    
    min_moves: int = Field(
        default=3,
        description="Minimum number of moves for random generation (for larger state space)"
    )
    
    max_moves: int = Field(
        default=10,
        description="Maximum number of moves for random generation (for larger state space)"
    )
    
    generation_method: str = Field(
        default="random",
        description="Generation method: 'reverse' (from goal state) or 'random' (random valid state)"
    )
    
    difficulty_distribution: Optional[dict] = Field(
        default=None,
        description="""Optional difficulty distribution dict for mixed configurations.
        Example: {
            "easy": {"size": 3, "min_moves": 3, "max_moves": 5, "weight": 0.3},
            "medium": {"size": 4, "min_moves": 5, "max_moves": 8, "weight": 0.4},
            "hard": {"size": 5, "min_moves": 8, "max_moves": 12, "weight": 0.3}
        }"""
    )
