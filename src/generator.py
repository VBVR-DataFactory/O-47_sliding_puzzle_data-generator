"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SLIDING PUZZLE TASK GENERATOR                              ║
║                                                                               ║
║  Generates sliding puzzles with scalable state space (3-20 moves)            ║
║  Supports both reverse generation (from goal) and random state generation     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import random
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from core import BaseGenerator, TaskPair, ImageRenderer
from core.video_utils import VideoGenerator
from .config import TaskConfig
from .prompts import get_prompt


class TaskGenerator(BaseGenerator):
    """
    Sliding puzzle task generator with scalable state space.
    
    Supports:
    - Reverse generation: from goal state, make N moves (3-20 steps)
    - Random generation: create random valid states
    - Mixed difficulty: support different sizes and move ranges
    """
    
    def __init__(self, config: TaskConfig):
        super().__init__(config)
        self.renderer = ImageRenderer(image_size=config.image_size)
        
        # Initialize video generator if enabled
        self.video_generator = None
        if config.generate_videos and VideoGenerator.is_available():
            self.video_generator = VideoGenerator(fps=config.video_fps, output_format="mp4")
        
        # Random number generator
        self.rng = random.Random()
        if config.random_seed is not None:
            self.rng.seed(config.random_seed)
        
        # Track seen states to ensure uniqueness
        self.seen_states: set = set()
    
    def state_to_tuple(self, state: List[List[int]]) -> Tuple:
        """Convert puzzle state to hashable tuple for uniqueness checking."""
        return tuple(tuple(row) for row in state)

    @staticmethod
    def _reverse_direction(direction: str) -> str:
        reverse_map = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
        return reverse_map[direction]

    @staticmethod
    def _tile_move_direction_from_blank_move(blank_move: str) -> str:
        # If blank moves up, the tile above moved down into the blank, etc.
        return TaskGenerator._reverse_direction(blank_move)

    def _apply_blank_move_inplace(
        self,
        puzzle: List[List[int]],
        blank_pos: Tuple[int, int],
        direction: str
    ) -> Tuple[List[List[int]], Tuple[int, int], int]:
        """
        Apply a move and return (new_puzzle, new_blank_pos, moved_tile_value).
        The direction refers to blank movement.
        """
        row, col = blank_pos
        if direction == 'up':
            swap_row, swap_col = row - 1, col
        elif direction == 'down':
            swap_row, swap_col = row + 1, col
        elif direction == 'left':
            swap_row, swap_col = row, col - 1
        elif direction == 'right':
            swap_row, swap_col = row, col + 1
        else:
            raise ValueError(f"Invalid direction: {direction}")

        moved_tile_value = puzzle[swap_row][swap_col]
        puzzle[row][col], puzzle[swap_row][swap_col] = puzzle[swap_row][swap_col], puzzle[row][col]
        return puzzle, (swap_row, swap_col), moved_tile_value

    def scramble_from_goal(
        self,
        size: int,
        num_moves: int,
        seed: Optional[int] = None
    ) -> Tuple[List[List[int]], List[str]]:
        """
        Create an initial state by starting from the goal and applying num_moves blank-moves.

        Returns:
            (initial_state, scramble_blank_moves)
        """
        old_state = None
        if seed is not None and hasattr(self.rng, 'getstate') and hasattr(self.rng, 'seed'):
            old_state = self.rng.getstate()
            self.rng.seed(seed)

        goal = self.create_goal_state(size)
        puzzle = [row[:] for row in goal]
        blank_pos = self.find_blank(puzzle)

        scramble_moves: List[str] = []
        last_direction: Optional[str] = None

        for _ in range(num_moves):
            valid_directions = self.get_valid_moves(puzzle, blank_pos)
            if last_direction and len(valid_directions) > 1:
                reverse = self._reverse_direction(last_direction)
                if reverse in valid_directions:
                    valid_directions.remove(reverse)
            if not valid_directions:
                break
            direction = self.rng.choice(valid_directions)
            puzzle, blank_pos, _moved_tile = self._apply_blank_move_inplace(puzzle, blank_pos, direction)
            scramble_moves.append(direction)
            last_direction = direction

        if old_state is not None and hasattr(self.rng, 'setstate'):
            self.rng.setstate(old_state)

        return puzzle, scramble_moves
    
    def generate_task_pair(
        self, 
        task_id: str, 
        max_retries: int = 200,
        puzzle_size: Optional[int] = None,
        min_moves: Optional[int] = None,
        max_moves: Optional[int] = None,
        generation_method: Optional[str] = None
    ) -> Optional[TaskPair]:
        """
        Generate one sliding puzzle task pair with uniqueness guarantee.
        
        Args:
            task_id: Unique identifier for the task
            max_retries: Maximum number of attempts to generate a unique state
            puzzle_size: Override config puzzle size
            min_moves: Override config min_moves
            max_moves: Override config max_moves
            generation_method: Override config generation_method
            
        Returns:
            TaskPair if unique state found, None if max retries exceeded
        """
        # Use provided parameters or fall back to config
        size = puzzle_size if puzzle_size is not None else self.config.puzzle_size
        min_m = min_moves if min_moves is not None else self.config.min_moves
        max_m = max_moves if max_moves is not None else self.config.max_moves
        method = generation_method if generation_method is not None else self.config.generation_method
        
        # Try to generate a unique puzzle state
        for attempt in range(max_retries):
            task_hash = abs(hash(task_id))
            if self.config.random_seed is not None:
                seed = self.config.random_seed + task_hash * 1000 + attempt * 17
            else:
                seed = task_hash * 1000 + attempt * 17

            # Pick an exact number of moves (this defines BOTH prompt and ground truth)
            num_moves = (seed % (max_m - min_m + 1)) + min_m

            # For scaling we support two labels, but both MUST return a true step sequence.
            # We generate by scrambling from goal so the exact solution is known.
            initial_state, scramble_blank_moves = self.scramble_from_goal(
                size, num_moves, seed=seed
            )
            solution_blank_moves = [self._reverse_direction(m) for m in reversed(scramble_blank_moves)]
            solution_length = len(solution_blank_moves)
            
            # Check uniqueness: state key is (puzzle_size, state_tuple)
            state_key = (size, self.state_to_tuple(initial_state))
            
            if state_key not in self.seen_states:
                # Unique state found!
                self.seen_states.add(state_key)
                break
            # Otherwise, try again
        else:
            # Max retries exceeded
            return None
        
        # Create goal state
        goal_state = self.create_goal_state(size)

        # Build step-by-step states by executing the solution moves from initial -> goal
        states: List[List[List[int]]] = []
        cur = [row[:] for row in initial_state]
        blank_pos = self.find_blank(cur)
        states.append([row[:] for row in cur])

        step_records: List[Dict[str, Any]] = []
        for step_idx, blank_move in enumerate(solution_blank_moves, start=1):
            before_blank = blank_pos
            cur, blank_pos, moved_tile = self._apply_blank_move_inplace(cur, blank_pos, blank_move)
            after_blank = blank_pos
            step_records.append({
                "step": step_idx,
                "blank_move": blank_move,
                "tile_moved": moved_tile,
                "tile_move_direction": self._tile_move_direction_from_blank_move(blank_move),
                "blank_from": list(before_blank),
                "blank_to": list(after_blank),
                "state": [row[:] for row in cur],
            })
            states.append([row[:] for row in cur])
        
        # Render images
        first_image = self.render_puzzle(initial_state, size)
        final_image = self.render_puzzle(goal_state, size)
        
        # Generate prompt with dynamic move count
        prompt = get_prompt("default", num_moves=solution_length)
        
        # Generate video (optional)
        video_path = None
        if self.config.generate_videos and self.video_generator:
            video_path = self._generate_video(
                first_image, final_image, task_id, 
                initial_state, goal_state, size, solution_length, states=states
            )

        # Metadata is set to None to ensure only required files are generated:
        # first_frame.png, final_frame.png, prompt.txt, and ground_truth.mp4
        metadata = None

        return TaskPair(
            task_id=task_id,
            domain=self.config.domain,
            prompt=prompt,
            first_image=first_image,
            final_image=final_image,
            ground_truth_video=video_path,
            metadata=metadata
        )
    
    # ══════════════════════════════════════════════════════════════════════════
    #  PUZZLE GENERATION METHODS
    # ══════════════════════════════════════════════════════════════════════════
    
    def create_goal_state(self, size: int) -> List[List[int]]:
        """
        Create the goal state (complete puzzle).
        
        Args:
            size: Puzzle size (3, 4, or 5)
            
        Returns:
            2D list representing the goal state
        """
        goal = []
        num = 1
        for i in range(size):
            row = []
            for j in range(size):
                if i == size - 1 and j == size - 1:
                    row.append(0)  # Empty space at bottom-right
                else:
                    row.append(num)
                    num += 1
            goal.append(row)
        return goal
    
    def find_blank(self, puzzle: List[List[int]]) -> Tuple[int, int]:
        """Find the position of the blank (0) in the puzzle."""
        for i in range(len(puzzle)):
            for j in range(len(puzzle[i])):
                if puzzle[i][j] == 0:
                    return (i, j)
        raise ValueError("No blank space found in puzzle")
    
    def get_valid_moves(self, puzzle: List[List[int]], blank_pos: Tuple[int, int]) -> List[str]:
        """
        Get valid move directions from the blank position.
        
        Args:
            puzzle: Current puzzle state
            blank_pos: (row, col) of blank space
            
        Returns:
            List of valid directions: ['up', 'down', 'left', 'right']
        """
        row, col = blank_pos
        size = len(puzzle)
        valid = []
        
        if row > 0:
            valid.append('up')
        if row < size - 1:
            valid.append('down')
        if col > 0:
            valid.append('left')
        if col < size - 1:
            valid.append('right')
        
        return valid
    
    def apply_move(self, puzzle: List[List[int]], blank_pos: Tuple[int, int], 
                   direction: str) -> Tuple[List[List[int]], Tuple[int, int]]:
        """
        Apply a move to the puzzle.
        
        Args:
            puzzle: Current puzzle state (will be modified)
            blank_pos: Current blank position
            direction: 'up', 'down', 'left', or 'right'
            
        Returns:
            (new_puzzle, new_blank_pos)
        """
        # Deep copy to avoid modifying original
        new_puzzle = [row[:] for row in puzzle]
        row, col = blank_pos
        
        # Determine swap position
        if direction == 'up':
            swap_row, swap_col = row - 1, col
        elif direction == 'down':
            swap_row, swap_col = row + 1, col
        elif direction == 'left':
            swap_row, swap_col = row, col - 1
        elif direction == 'right':
            swap_row, swap_col = row, col + 1
        else:
            raise ValueError(f"Invalid direction: {direction}")
        
        # Swap blank with adjacent tile
        new_puzzle[row][col], new_puzzle[swap_row][swap_col] = \
            new_puzzle[swap_row][swap_col], new_puzzle[row][col]
        
        return new_puzzle, (swap_row, swap_col)
    
    def generate_near_complete_puzzle(self, size: int, num_moves: int, seed: Optional[int] = None) -> Tuple[List[List[int]], int]:
        """
        Generate a puzzle by starting from goal state and making N moves.
        
        Args:
            size: Puzzle size (3, 4, or 5)
            num_moves: Number of moves to make from goal state (1-20)
            seed: Optional random seed for this generation
            
        Returns:
            (puzzle_state, solution_length)
        """
        # Temporarily set seed if provided
        old_state = None
        if seed is not None:
            if hasattr(self.rng, 'getstate'):
                old_state = self.rng.getstate()
            if hasattr(self.rng, 'seed'):
                self.rng.seed(seed)
        
        # Start from goal state
        goal = self.create_goal_state(size)
        puzzle = [row[:] for row in goal]  # Deep copy
        blank_pos = self.find_blank(puzzle)
        
        # Make num_moves random moves (reverse from goal)
        moves = []
        last_direction = None
        
        for _ in range(num_moves):
            valid_directions = self.get_valid_moves(puzzle, blank_pos)
            
            # Avoid moving back to previous position (unless it's the only option)
            if last_direction and len(valid_directions) > 1:
                # Remove the reverse direction
                reverse_map = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
                reverse = reverse_map.get(last_direction)
                if reverse in valid_directions:
                    valid_directions.remove(reverse)
            
            if not valid_directions:
                break
            
            direction = self.rng.choice(valid_directions)
            puzzle, blank_pos = self.apply_move(puzzle, blank_pos, direction)
            moves.append(direction)
            last_direction = direction
        
        # Restore random state
        if old_state and hasattr(self.rng, 'setstate'):
            self.rng.setstate(old_state)
        
        # Solution length equals number of moves made (reverse them to solve)
        solution_length = len(moves)
        
        return puzzle, solution_length
    
    def generate_random_puzzle(self, size: int, min_moves: int, max_moves: int, seed: Optional[int] = None) -> Tuple[List[List[int]], int]:
        """
        Generate a random valid puzzle state by randomizing from goal state.
        
        This creates a much larger state space than reverse generation.
        
        Args:
            size: Puzzle size (3, 4, or 5)
            min_moves: Minimum number of moves from goal (for solution length estimate)
            max_moves: Maximum number of moves from goal
            seed: Optional random seed
            
        Returns:
            (puzzle_state, estimated_solution_length)
        """
        # Temporarily set seed if provided
        old_state = None
        if seed is not None:
            if hasattr(self.rng, 'getstate'):
                old_state = self.rng.getstate()
            if hasattr(self.rng, 'seed'):
                self.rng.seed(seed)
        
        # Start from goal state
        goal = self.create_goal_state(size)
        puzzle = [row[:] for row in goal]
        blank_pos = self.find_blank(puzzle)
        
        # Make many random moves to create a diverse state
        # Use a number between min_moves and max_moves, but make more moves
        # to ensure good randomization
        num_randomization_moves = max_moves * 3  # Make 3x more moves for better randomization
        
        last_direction = None
        for _ in range(num_randomization_moves):
            valid_directions = self.get_valid_moves(puzzle, blank_pos)
            
            # Avoid immediate backtracking
            if last_direction and len(valid_directions) > 1:
                reverse_map = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
                reverse = reverse_map.get(last_direction)
                if reverse in valid_directions:
                    valid_directions.remove(reverse)
            
            if not valid_directions:
                break
            
            direction = self.rng.choice(valid_directions)
            puzzle, blank_pos = self.apply_move(puzzle, blank_pos, direction)
            last_direction = direction
        
        # Restore random state
        if old_state and hasattr(self.rng, 'setstate'):
            self.rng.setstate(old_state)
        
        # Estimate solution length (will be calculated by solver if needed)
        # For now, use a value in the min-max range
        estimated_length = self.rng.randint(min_moves, max_moves) if seed is None else \
            (seed % (max_moves - min_moves + 1)) + min_moves
        
        return puzzle, estimated_length
    
    # ══════════════════════════════════════════════════════════════════════════
    #  RENDERING METHODS
    # ══════════════════════════════════════════════════════════════════════════
    
    def render_puzzle(self, puzzle: List[List[int]], size: int) -> Image.Image:
        """
        Render the puzzle as a PIL Image.
        
        Args:
            puzzle: 2D list representing puzzle state
            size: Puzzle size (3, 4, or 5)
            
        Returns:
            PIL Image of the puzzle
        """
        canvas_size = self.config.image_size[0]
        
        # Create figure with white background
        fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
        ax.set_xlim(0, size)
        ax.set_ylim(0, size)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        
        # Draw grid lines
        for i in range(size + 1):
            # Vertical lines
            ax.plot([i, i], [0, size], '-', linewidth=2, color='#333333')
            # Horizontal lines
            ax.plot([0, size], [i, i], '-', linewidth=2, color='#333333')
        
        # Calculate tile size
        tile_size = 0.9  # Slightly smaller than 1 to show grid lines
        margin = (1 - tile_size) / 2
        
        # Adjust font size based on puzzle size
        if size == 3:
            fontsize = 32
        elif size == 4:
            fontsize = 24
        else:  # size == 5
            fontsize = 20
        
        # Draw tiles
        for i in range(size):
            for j in range(size):
                value = puzzle[i][j]
                x = j + margin
                y = size - 1 - i + margin  # Flip Y axis
                
                if value == 0:
                    # Empty space - white background (no tile, just grid lines)
                    pass
                else:
                    # Numbered tile - draw as colored rectangle
                    rect = patches.Rectangle(
                        (x, y), tile_size, tile_size,
                        linewidth=2, edgecolor='#333333', facecolor='#4A90E2'
                    )
                    ax.add_patch(rect)
                    # Add number
                    ax.text(x + tile_size/2, y + tile_size/2, str(value),
                           ha='center', va='center', fontsize=fontsize, 
                           color='white', weight='bold')
        
        # Save to temporary buffer and convert to PIL Image
        import io
        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, dpi=100, bbox_inches='tight', facecolor='white', format='png')
        plt.close(fig)
        buf.seek(0)
        img = Image.open(buf).convert('RGB')
        
        # Resize to desired canvas size
        if img.size[0] != canvas_size:
            img = img.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)
        
        return img
    
    # ══════════════════════════════════════════════════════════════════════════
    #  VIDEO GENERATION
    # ══════════════════════════════════════════════════════════════════════════
    
    def _generate_video(
        self,
        first_image: Image.Image,
        final_image: Image.Image,
        task_id: str,
        initial_state: List[List[int]],
        goal_state: List[List[int]],
        puzzle_size: int,
        solution_length: int,
        states: Optional[List[List[List[int]]]] = None
    ) -> Optional[str]:
        """Generate ground truth video showing tile sliding animation."""
        temp_dir = Path(tempfile.gettempdir()) / f"{self.config.domain}_videos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        video_path = temp_dir / f"{task_id}_ground_truth.mp4"
        
        # Create animation frames showing step-by-step solution
        frames = self._create_stepwise_animation_frames(
            initial_state, goal_state, puzzle_size, states=states
        )
        
        if frames:
            result = self.video_generator.create_video_from_frames(
                frames,
                video_path
            )
            return str(result) if result else None
        
        return None

    def _create_stepwise_animation_frames(
        self,
        initial_state: List[List[int]],
        goal_state: List[List[int]],
        puzzle_size: int,
        states: Optional[List[List[List[int]]]] = None,
        hold_frames: int = 5,
        transition_frames_per_step: int = 8,
    ) -> List[Image.Image]:
        """
        Create a stepwise animation: initial -> each intermediate state -> goal.

        This is intentionally step-aligned so it matches `question_metadata.json` steps.
        (We use crossfade between successive states; each step is a real legal move.)
        """
        if states is None or len(states) < 2:
            # Fallback to simple crossfade
            return self._create_sliding_animation_frames(
                initial_state, goal_state, puzzle_size, solution_length=1
            )

        frames: List[Image.Image] = []

        # Hold initial
        first_img = self.render_puzzle(states[0], puzzle_size)
        for _ in range(hold_frames):
            frames.append(first_img.copy())

        # Transition per step
        for idx in range(len(states) - 1):
            a = self.render_puzzle(states[idx], puzzle_size).convert("RGBA")
            b = self.render_puzzle(states[idx + 1], puzzle_size).convert("RGBA")
            for t in range(transition_frames_per_step):
                alpha = t / (transition_frames_per_step - 1) if transition_frames_per_step > 1 else 1.0
                frames.append(Image.blend(a, b, alpha).convert("RGB"))

        # Hold final
        last_img = self.render_puzzle(states[-1], puzzle_size)
        for _ in range(hold_frames):
            frames.append(last_img.copy())

        return frames
    
    def _create_sliding_animation_frames(
        self,
        initial_state: List[List[int]],
        goal_state: List[List[int]],
        puzzle_size: int,
        solution_length: int,
        hold_frames: int = 5,
        transition_frames: int = 25
    ) -> List[Image.Image]:
        """
        Create animation frames showing tiles sliding from initial to goal state.
        
        This creates a smooth animation where tiles slide into their final positions.
        """
        frames = []
        
        # Hold initial position
        initial_img = self.render_puzzle(initial_state, puzzle_size)
        for _ in range(hold_frames):
            frames.append(initial_img.copy())
        
        # Find which tile needs to move
        # Compare initial and goal states to find the moving tile
        moving_tile_value = None
        from_pos = None
        to_pos = None
        
        for i in range(puzzle_size):
            for j in range(puzzle_size):
                if initial_state[i][j] != goal_state[i][j]:
                    if initial_state[i][j] != 0:
                        moving_tile_value = initial_state[i][j]
                        from_pos = (i, j)
                    if goal_state[i][j] != 0:
                        # Find where this tile should be
                        for ii in range(puzzle_size):
                            for jj in range(puzzle_size):
                                if initial_state[ii][jj] == goal_state[i][j]:
                                    to_pos = (i, j)
                                    break
        
        # If we can't determine the move, use simple crossfade
        if moving_tile_value is None or from_pos is None or to_pos is None:
            goal_img = self.render_puzzle(goal_state, puzzle_size)
            for _ in range(transition_frames):
                frames.append(initial_img.copy())
            for _ in range(hold_frames):
                frames.append(goal_img.copy())
            return frames
        
        # Create transition frames with sliding animation
        # For simplicity, we'll use a crossfade between states
        # A more sophisticated implementation would animate individual tiles
        goal_img = self.render_puzzle(goal_state, puzzle_size)
        
        initial_rgba = initial_img.convert('RGBA')
        goal_rgba = goal_img.convert('RGBA')
        
        for i in range(transition_frames):
            progress = i / (transition_frames - 1) if transition_frames > 1 else 1.0
            blended = Image.blend(initial_rgba, goal_rgba, progress)
            frames.append(blended.convert('RGB'))
        
        # Hold final position
        for _ in range(hold_frames):
            frames.append(goal_img.copy())
        
        return frames
    
    # ══════════════════════════════════════════════════════════════════════════
    #  DATASET GENERATION WITH UNIQUENESS
    # ══════════════════════════════════════════════════════════════════════════
    
    def generate_dataset(self) -> List[TaskPair]:
        """
        Generate complete dataset with uniqueness guarantee.
        
        Supports both single configuration and mixed difficulty distributions.
        """
        pairs = []
        max_retries_per_task = 200
        
        # Check if using difficulty distribution
        if self.config.difficulty_distribution:
            return self._generate_dataset_with_distribution()
        
        # Single configuration generation
        print(f"🧩 Generating {self.config.num_samples} unique sliding puzzle tasks...")
        print(f"   Puzzle size: {self.config.puzzle_size}×{self.config.puzzle_size}")
        print(f"   Generation method: {self.config.generation_method}")
        print(f"   Moves range: {self.config.min_moves}-{self.config.max_moves}")
        
        for i in range(self.config.num_samples):
            task_id = f"{self.config.domain}_{i:04d}"
            
            pair = self.generate_task_pair(
                task_id, 
                max_retries=max_retries_per_task,
                puzzle_size=self.config.puzzle_size,
                min_moves=self.config.min_moves,
                max_moves=self.config.max_moves,
                generation_method=self.config.generation_method
            )
            
            if pair is not None:
                pairs.append(pair)
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"  ✅ Generated: {task_id} ({len(pairs)}/{self.config.num_samples})")
            else:
                # Try a few more times with different seeds
                for retry in range(5):
                    pair = self.generate_task_pair(
                        task_id, 
                        max_retries=50,
                        puzzle_size=self.config.puzzle_size,
                        min_moves=self.config.min_moves,
                        max_moves=self.config.max_moves,
                        generation_method=self.config.generation_method
                    )
                    if pair is not None:
                        pairs.append(pair)
                        break
        
        print(f"✅ Generated {len(pairs)} unique sliding puzzle tasks")
        print(f"   Unique states: {len(self.seen_states)}")
        
        if len(pairs) < self.config.num_samples:
            print(f"   ⚠️  Warning: Only generated {len(pairs)}/{self.config.num_samples} tasks")
            print(f"      Consider increasing max_moves or using 'random' generation method for larger state space.")
        
        return pairs
    
    def _generate_dataset_with_distribution(self) -> List[TaskPair]:
        """
        Generate dataset with mixed difficulty distribution.
        
        Supports different puzzle sizes and move ranges in a single dataset.
        """
        pairs = []
        max_retries_per_task = 200
        
        dist = self.config.difficulty_distribution
        total_weight = sum(d.get("weight", 1.0) for d in dist.values())
        
        print(f"🧩 Generating {self.config.num_samples} unique sliding puzzle tasks...")
        print(f"   Using mixed difficulty distribution:")
        
        # Calculate samples per difficulty
        difficulty_samples = {}
        remaining = self.config.num_samples
        
        for difficulty, config in dist.items():
            weight = config.get("weight", 1.0) / total_weight
            count = int(self.config.num_samples * weight)
            difficulty_samples[difficulty] = {
                "count": count,
                "config": config
            }
            remaining -= count
            print(f"   - {difficulty}: {count} samples (size={config['size']}, moves={config['min_moves']}-{config['max_moves']})")
        
        # Distribute remaining samples
        if remaining > 0:
            difficulties = list(difficulty_samples.keys())
            for i in range(remaining):
                difficulty_samples[difficulties[i % len(difficulties)]]["count"] += 1
        
        # Generate tasks for each difficulty
        task_idx = 0
        for difficulty, info in difficulty_samples.items():
            count = info["count"]
            config = info["config"]
            
            size = config["size"]
            min_moves = config["min_moves"]
            max_moves = config["max_moves"]
            method = config.get("generation_method", self.config.generation_method)
            
            print(f"\n   Generating {count} {difficulty} tasks...")
            
            for i in range(count):
                task_id = f"{self.config.domain}_{task_idx:04d}"
                
                pair = self.generate_task_pair(
                    task_id,
                    max_retries=max_retries_per_task,
                    puzzle_size=size,
                    min_moves=min_moves,
                    max_moves=max_moves,
                    generation_method=method
                )
                
                if pair is not None:
                    pairs.append(pair)
                    task_idx += 1
                    if (i + 1) % 10 == 0 or i == 0:
                        print(f"     ✅ {difficulty}: {task_id} ({i+1}/{count})")
                else:
                    # Retry with different approach
                    for retry in range(5):
                        pair = self.generate_task_pair(
                            task_id,
                            max_retries=50,
                            puzzle_size=size,
                            min_moves=min_moves,
                            max_moves=max_moves,
                            generation_method=method
                        )
                        if pair is not None:
                            pairs.append(pair)
                            task_idx += 1
                            break
        
        print(f"\n✅ Generated {len(pairs)} unique sliding puzzle tasks")
        print(f"   Unique states: {len(self.seen_states)}")
        
        return pairs
