"""
Core utilities for template-data-generator.

This module provides the standard framework for data generators following the
template-data-generator format. It is based on the template from:
https://github.com/vm-dataset/template-data-generator.git

DO NOT MODIFY - This is framework code.
Customize files in src/ for your task.
"""

from .base_generator import BaseGenerator, GenerationConfig
from .schemas import TaskPair
from .image_utils import ImageRenderer
from .output_writer import OutputWriter
from .video_utils import VideoGenerator

__all__ = [
    "BaseGenerator",
    "GenerationConfig",
    "TaskPair",
    "ImageRenderer",
    "OutputWriter",
    "VideoGenerator",
]
