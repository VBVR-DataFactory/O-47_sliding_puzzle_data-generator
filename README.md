# Sliding Puzzle Task Data Generator

A data generator for creating sliding puzzle reasoning tasks for video model evaluation. This task is based on [VMEvalKit](https://github.com/Video-Reason/VMEvalKit.git) and follows the format standard of [template-data-generator](https://github.com/vm-dataset/template-data-generator.git).

Generates near-complete sliding puzzles (1-2 moves from solution) that test spatial reasoning, simple planning, and visual consistency in video generation models.

Repository: [O_47_sliding_puzzle_data_generator](https://github.com/vm-dataset/O_47_sliding_puzzle_data_generator)

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/vm-dataset/O_47_sliding_puzzle_data_generator.git
cd O_47_sliding_puzzle_data_generator

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Generate sliding puzzle tasks
python3 examples/generate.py --num-samples 50

# Generate with custom puzzle size and moves
python3 examples/generate.py --num-samples 50 --output data/my_puzzles
```

## Project Structure

```
sliding-puzzle-task-data-generator/
├── core/                    # Standard utilities (template framework)
│   ├── base_generator.py   # Abstract base class
│   ├── schemas.py          # Pydantic models
│   ├── image_utils.py      # Image helpers
│   ├── video_utils.py      # Video generation
│   └── output_writer.py    # File output
├── src/                     # Task-specific implementation
│   ├── generator.py        # Sliding puzzle generator
│   ├── prompts.py          # Sliding puzzle prompts
│   └── config.py           # Sliding puzzle configuration
├── examples/                # Example generation scripts
│   ├── generate.py         # Basic entry point
│   └── generate_large_dataset.py  # Large-scale generation
└── data/questions/         # Generated output directory
```

## Output Format

Every generator produces tasks in the following structure:

```
data/questions/{domain}_task/{task_id}/
├── first_frame.png          # Initial state (REQUIRED)
├── final_frame.png          # Goal state (REQUIRED)
├── prompt.txt               # Task instructions (REQUIRED)
├── ground_truth.mp4         # Solution video (OPTIONAL)
└── question_metadata.json   # Task metadata (OPTIONAL)
```

## Task Description

This generator creates sliding puzzles with scalable state space (3-20 moves) for video model evaluation. Supports both reverse generation (from goal state) and random state generation for maximum diversity.

**Key Features:**
- Spatial Reasoning: Understanding 2D grid space and tile positions
- Planning: Identifying which tiles need to move (3-20 moves)
- Visual Consistency: Maintaining tile appearance during sliding animation
- Scalable: Generate hundreds or thousands of unique tasks

### Configuration Options

In `src/config.py`, you can customize:
- `puzzle_size`: 3, 4, or 5 (for 3×3, 4×4, or 5×5 puzzles)
- `min_moves`: Minimum number of moves (default: 3, for larger state space)
- `max_moves`: Maximum number of moves (default: 10, can go up to 20)
- `generation_method`: `"reverse"` (from goal state) or `"random"` (random valid states)
- `difficulty_distribution`: Optional dict for mixed configurations
- `image_size`: Canvas size in pixels (default: 400×400)
- `generate_videos`: Whether to generate ground truth videos

### Example Usage

**For small to medium datasets (<500 tasks):**
```bash
# Generate 100 puzzles with random states
python3 examples/generate.py --num-samples 100

# Generate without videos (faster)
python3 examples/generate.py --num-samples 500 --no-videos
```

**For large-scale datasets (1000+ tasks):**
```bash
# Generate 1000 tasks with mixed difficulty (recommended)
python3 examples/generate_large_dataset.py --num-samples 1000 --mixed --no-videos

# Generate 5000 tasks, single size
python3 examples/generate_large_dataset.py --num-samples 5000 --size 4 --no-videos

# Generate 10000 tasks with custom configuration
python3 examples/generate_large_dataset.py --num-samples 10000 --mixed --no-videos --output data/large_dataset
```

## Task Details

### Puzzle Generation Methods

The generator supports two methods for creating puzzles:

1. **Reverse Generation** (`generation_method="reverse"`):
   - Starts from the goal state (numbers in order, empty space at bottom-right)
   - Makes N random reverse moves (N = min_moves to max_moves)
   - Avoids immediate backtracking to ensure diversity
   - Good for controlled difficulty levels

2. **Random Generation** (`generation_method="random"`):
   - Creates random valid puzzle states by extensive randomization
   - Makes 3×max_moves random moves from goal state
   - Provides much larger state space
   - **Recommended for generating many unique tasks**

### Uniqueness Guarantee

The generator automatically ensures all generated puzzles are unique:
- Tracks all generated states using a hash-based system
- Automatically retries if a duplicate state is generated
- Supports up to thousands of unique tasks with random generation

### State Space Scaling

With the new scaling design:
- **3×3 puzzles, random method, 3-10 moves**: Can generate 100+ unique tasks
- **4×4 puzzles, random method, 5-12 moves**: Can generate 500+ unique tasks
- **5×5 puzzles, random method, 8-15 moves**: Can generate 1000+ unique tasks

### Output Structure

Each generated task includes:
- `first_frame.png`: The near-complete puzzle state (1-2 moves from solution)
- `final_frame.png`: The complete solution state
- `prompt.txt`: Instructions for the video model
- `ground_truth.mp4`: Optional animation showing the solution (if video generation is enabled)

## Configuration

### Basic Configuration

All configuration is done in `src/config.py`:

```python
class TaskConfig(GenerationConfig):
    domain: str = "sliding_puzzle"
    puzzle_size: int = 3          # 3, 4, or 5
    min_moves: int = 3            # Minimum moves (3-20)
    max_moves: int = 10           # Maximum moves (3-20)
    generation_method: str = "random"  # "reverse" or "random"
    image_size: tuple[int, int] = (400, 400)
    generate_videos: bool = True
```

### Mixed Difficulty Distribution

For generating datasets with mixed configurations:

```python
config = TaskConfig(
    num_samples=1000,
    difficulty_distribution={
        'easy': {
            'size': 3,
            'min_moves': 3,
            'max_moves': 5,
            'weight': 0.3,
            'generation_method': 'random'
        },
        'medium': {
            'size': 4,
            'min_moves': 5,
            'max_moves': 8,
            'weight': 0.4,
            'generation_method': 'random'
        },
        'hard': {
            'size': 5,
            'min_moves': 8,
            'max_moves': 12,
            'weight': 0.3,
            'generation_method': 'random'
        }
    }
)
```

This will generate 1000 tasks with:
- 300 easy tasks (3×3, 3-5 moves)
- 400 medium tasks (4×4, 5-8 moves)
- 300 hard tasks (5×5, 8-12 moves)

## License

See LICENSE file for details.

## Reference

- [VMEvalKit](https://github.com/Video-Reason/VMEvalKit.git) - Video Model Evaluation Kit
- [template-data-generator](https://github.com/vm-dataset/template-data-generator.git) - Data generator template