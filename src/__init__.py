"""
Sliding Puzzle Task Data Generator

This module implements a data generator for creating sliding puzzle reasoning tasks
for video model evaluation. This task is based on VMEvalKit and follows the format
standard of template-data-generator.

It generates near-complete puzzles (1-2 moves from solution) that test spatial
reasoning, simple planning, and visual consistency.

Main components:
    - config.py   : Sliding puzzle configuration (TaskConfig)
    - generator.py: Sliding puzzle generation logic (TaskGenerator)
    - prompts.py  : Sliding puzzle prompts/instructions (get_prompt)

Reference:
    - VMEvalKit: https://github.com/Video-Reason/VMEvalKit.git
    - template-data-generator: https://github.com/vm-dataset/template-data-generator.git
"""

from .config import TaskConfig
from .generator import TaskGenerator
from .prompts import get_prompt

__all__ = ["TaskConfig", "TaskGenerator", "get_prompt"]
