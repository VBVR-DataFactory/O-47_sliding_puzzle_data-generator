"""Setup script."""

from setuptools import setup, find_packages
from pathlib import Path

readme = Path("README.md").read_text() if Path("README.md").exists() else ""

requirements = []
if Path("requirements.txt").exists():
    with open("requirements.txt") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="sliding-puzzle-task-data-generator",
    version="1.0.0",
    description="Data generator for sliding puzzle reasoning tasks for video model evaluation",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="VMEvalKit Contributors",
    url="https://github.com/vm-dataset/O_47_sliding_puzzle_data_generator",
    packages=find_packages(include=["core", "core.*", "src", "src.*"]),
    python_requires=">=3.8",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
