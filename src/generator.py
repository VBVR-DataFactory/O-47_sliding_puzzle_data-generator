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
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from core import BaseGenerator, TaskPair, ImageRenderer
from core.video_utils import VideoGenerator
from .config import TaskConfig
from .prompts import get_prompt


# Color themes for puzzle tiles (for scaling)
COLOR_THEMES = {
    'blue': '#4A90E2',
    'green': '#52C41A',
    'red': '#F5222D',
    'purple': '#722ED1',
    'orange': '#FA8C16',
    'cyan': '#13C2C2',
    'pink': '#EB2F96',
    'gold': '#FAAD14',
    'lime': '#A0D911',
    'magenta': '#C41D7F',
}


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
        
        # Select tile color theme
        if self.config.tile_color_theme == "random":
            # Randomly select from available color themes
            color_names = list(COLOR_THEMES.keys())
            tile_color_name = self.rng.choice(color_names)
            tile_color = COLOR_THEMES[tile_color_name]
        elif self.config.tile_color_theme in COLOR_THEMES:
            tile_color_name = self.config.tile_color_theme
            tile_color = COLOR_THEMES[tile_color_name]
        else:
            # Fallback to blue if invalid color specified
            tile_color_name = 'blue'
            tile_color = COLOR_THEMES['blue']
        
        # Try to generate a unique puzzle state
        # Use deterministic seed based on task_id for reproducibility
        task_hash = abs(hash(task_id))
        if self.config.random_seed is not None:
            base_seed = self.config.random_seed + task_hash * 1000
        else:
            base_seed = task_hash * 1000
        
        # Add size and color to seed to ensure different puzzles for different configs
        base_seed += size * 100000 + abs(hash(tile_color_name)) % 10000
        
        for attempt in range(max_retries):
            # Only vary seed if we need to retry for uniqueness
            seed = base_seed + attempt * 17

            # Pick an exact number of moves (this defines BOTH prompt and ground truth)
            num_moves = (seed % (max_m - min_m + 1)) + min_m

            # For scaling we support two labels, but both MUST return a true step sequence.
            # We generate by scrambling from goal so the exact solution is known.
            initial_state, scramble_blank_moves = self.scramble_from_goal(
                size, num_moves, seed=seed
            )
            solution_blank_moves = [self._reverse_direction(m) for m in reversed(scramble_blank_moves)]
            solution_length = len(solution_blank_moves)
            
            # Check uniqueness: state key includes size, state, and color
            state_key = (size, self.state_to_tuple(initial_state), tile_color_name)
            
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
        
        # Render images with selected tile color
        first_image = self.render_puzzle(initial_state, size, tile_color=tile_color)
        final_image = self.render_puzzle(goal_state, size, tile_color=tile_color)
        
        # Generate prompt with dynamic move count
        prompt = get_prompt("default", num_moves=solution_length)
        
        # Generate video (optional)
        video_path = None
        if self.config.generate_videos and self.video_generator:
            video_path = self._generate_video(
                first_image, final_image, task_id, 
                initial_state, goal_state, size, solution_length, states=states, tile_color=tile_color
            )

        # Build task_data dict from parameters
        task_data = {
            "size": size,
            "min_moves": min_m,
            "max_moves": max_m,
            "solution_length": solution_length,
            "tile_color_theme": tile_color_name,
            "generation_method": method,
            "initial_state": initial_state,
            "goal_state": goal_state,
            "step_records": step_records
        }
        
        # Build object-centric metadata
        optimized_task_data = self._build_objects_metadata(
            task_data, initial_state, goal_state, size
        )

        metadata = self._build_metadata(task_id, optimized_task_data)

        

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
    
    def _create_fixed_figure(self, puzzle_size: int, tile_color: str):
        """
        Create a figure with fixed layout parameters (no bbox_inches='tight').
        This is faster for animation frames.
        """
        fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
        ax.set_xlim(0, puzzle_size)
        ax.set_ylim(0, puzzle_size)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        
        # Use fixed tight layout without bbox_inches='tight'
        # This is much faster and ensures consistent dimensions
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        
        return fig, ax
    
    def render_puzzle(self, puzzle: List[List[int]], size: int, tile_color: str = '#4A90E2') -> Image.Image:
        """
        Render the puzzle as a PIL Image using fast PIL rendering.
        
        Args:
            puzzle: 2D list representing puzzle state
            size: Puzzle size (3, 4, or 5)
            tile_color: Hex color code for tile background (default: blue)
            
        Returns:
            PIL Image of the puzzle
        """
        canvas_size = self.config.image_size[0]
        
        # Convert hex color to RGB
        if tile_color.startswith('#'):
            tile_rgb = tuple(int(tile_color[i:i+2], 16) for i in (1, 3, 5))
        else:
            tile_rgb = (74, 144, 226)  # Default blue
        
        # Create image with white background
        img = Image.new('RGB', (canvas_size, canvas_size), 'white')
        draw = ImageDraw.Draw(img)
        
        # Calculate tile size and spacing
        grid_padding = canvas_size * 0.02  # 2% padding - minimal for full screen
        grid_size = canvas_size - 2 * grid_padding
        cell_size = grid_size / size
        tile_size = cell_size * 0.9  # 90% of cell to show grid lines
        tile_margin = (cell_size - tile_size) / 2
        
        # Grid line width
        grid_line_width = max(2, int(canvas_size / 512))
        
        # Draw grid lines
        grid_color = (51, 51, 51)  # #333333
        for i in range(size + 1):
            x = grid_padding + i * cell_size
            y = grid_padding + i * cell_size
            # Vertical lines
            draw.line([(x, grid_padding), (x, grid_padding + grid_size)], 
                     fill=grid_color, width=grid_line_width)
            # Horizontal lines
            draw.line([(grid_padding, y), (grid_padding + grid_size, y)], 
                     fill=grid_color, width=grid_line_width)
        
        # Font size based on puzzle size
        if size == 3:
            font_size = int(canvas_size / 20)  # Larger font for 3x3
        elif size == 4:
            font_size = int(canvas_size / 25)  # Larger font for 4x4
        else:  # size == 5
            font_size = int(canvas_size / 30)  # Larger font for 5x5
        
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        # Draw tiles
        for i in range(size):
            for j in range(size):
                value = puzzle[i][j]
                
                if value == 0:
                    # Empty space - skip (white background already set)
                    continue
                
                # Calculate tile position
                x = grid_padding + j * cell_size + tile_margin
                y = grid_padding + i * cell_size + tile_margin  # i=0 is top, i=size-1 is bottom
                
                # Draw tile rectangle
                draw.rectangle(
                    [x, y, x + tile_size, y + tile_size],
                    fill=tile_rgb,
                    outline=grid_color,
                    width=grid_line_width
                )
                
                # Draw number text
                text = str(value)
                # Get text bounding box for centering
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                text_x = x + (tile_size - text_width) / 2
                text_y = y + (tile_size - text_height) / 2
                
                draw.text((text_x, text_y), text, fill='white', font=font)
        
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
        states: Optional[List[List[List[int]]]] = None,
        tile_color: str = '#4A90E2'
    ) -> Optional[str]:
        """Generate ground truth video showing tile sliding animation."""
        temp_dir = Path(tempfile.gettempdir()) / f"{self.config.domain}_videos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        video_path = temp_dir / f"{task_id}_ground_truth.mp4"
        
        # Create animation frames showing step-by-step solution
        frames = self._create_stepwise_animation_frames(
            initial_state, goal_state, puzzle_size, states=states, tile_color=tile_color
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
        transition_frames_per_step: int = 6,  # Reduced from 10 for faster generation
        tile_color: str = '#4A90E2'
    ) -> List[Image.Image]:
        """
        Create a stepwise animation with real tile sliding effect.

        This creates a smooth sliding animation where each tile physically moves
        from its current position to its target position.
        """
        if states is None or len(states) < 2:
            return []

        frames: List[Image.Image] = []

        # Hold initial
        first_img = self.render_puzzle(states[0], puzzle_size, tile_color=tile_color)
        for _ in range(hold_frames):
            frames.append(first_img.copy())

        # Animate each step with real sliding
        for idx in range(len(states) - 1):
            state_before = states[idx]
            state_after = states[idx + 1]
            
            # Find blank position (optimized: track position instead of searching)
            if idx == 0:
                blank_before = self.find_blank(state_before)
            else:
                # blank_before is the blank_after from previous iteration
                blank_before = blank_after
            blank_after = self.find_blank(state_after)
            
            # The tile that moved:
            # In state_before, blank is at blank_before
            # In state_after, blank is at blank_after
            # So the tile moved FROM blank_after TO blank_before
            # The tile value is at blank_after in state_before
            from_row, from_col = blank_after
            to_row, to_col = blank_before
            tile_to_move = state_before[from_row][from_col]
            
            if tile_to_move != 0:
                # Generate sliding frames
                slide_frames = self._create_single_tile_slide_frames(
                    state_before, puzzle_size, tile_to_move,
                    from_row, from_col, to_row, to_col,
                    transition_frames_per_step, tile_color
                )
                frames.extend(slide_frames)

        # Hold final
        last_img = self.render_puzzle(states[-1], puzzle_size, tile_color=tile_color)
        for _ in range(hold_frames):
            frames.append(last_img.copy())

        return frames
    
    def _create_single_tile_slide_frames(
        self,
        state: List[List[int]],
        puzzle_size: int,
        tile_value: int,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
        num_frames: int,
        tile_color: str
    ) -> List[Image.Image]:
        """
        Create frames showing a single tile sliding from one position to another.
        Uses fast PIL rendering instead of matplotlib.
        """
        frames = []
        canvas_size = self.config.image_size[0]
        
        # Convert hex color to RGB
        if tile_color.startswith('#'):
            tile_rgb = tuple(int(tile_color[i:i+2], 16) for i in (1, 3, 5))
        else:
            tile_rgb = (74, 144, 226)  # Default blue
        
        # Calculate positions
        grid_padding = canvas_size * 0.02  # 2% padding - minimal for full screen
        grid_size = canvas_size - 2 * grid_padding
        cell_size = grid_size / puzzle_size
        tile_size = cell_size * 0.9
        tile_margin = (cell_size - tile_size) / 2
        
        grid_line_width = max(2, int(canvas_size / 512))
        grid_color = (51, 51, 51)
        
        # Font size
        if puzzle_size == 3:
            font_size = int(canvas_size / 20)  # Larger font for 3x3
        elif puzzle_size == 4:
            font_size = int(canvas_size / 25)  # Larger font for 4x4
        else:
            font_size = int(canvas_size / 30)  # Larger font for 5x5
        
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        # Pre-render static background (grid + static tiles)
        base_img = Image.new('RGB', (canvas_size, canvas_size), 'white')
        base_draw = ImageDraw.Draw(base_img)
        
        # Draw grid lines
        for i in range(puzzle_size + 1):
            x = grid_padding + i * cell_size
            y = grid_padding + i * cell_size
            base_draw.line([(x, grid_padding), (x, grid_padding + grid_size)], 
                          fill=grid_color, width=grid_line_width)
            base_draw.line([(grid_padding, y), (grid_padding + grid_size, y)], 
                          fill=grid_color, width=grid_line_width)
        
        # Draw static tiles (excluding moving tile and blank)
        for i in range(puzzle_size):
            for j in range(puzzle_size):
                value = state[i][j]
                if value == 0 or value == tile_value:
                    continue
                
                x = grid_padding + j * cell_size + tile_margin
                y = grid_padding + i * cell_size + tile_margin  # i=0 is top, i=size-1 is bottom
                
                base_draw.rectangle(
                    [x, y, x + tile_size, y + tile_size],
                    fill=tile_rgb,
                    outline=grid_color,
                    width=grid_line_width
                )
                
                text = str(value)
                bbox = base_draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = x + (tile_size - text_width) / 2
                text_y = y + (tile_size - text_height) / 2
                base_draw.text((text_x, text_y), text, fill='white', font=font)
        
        # Generate animation frames
        for frame_idx in range(num_frames):
            # Calculate interpolation progress (0.0 to 1.0)
            t = frame_idx / (num_frames - 1) if num_frames > 1 else 1.0
            # Use smooth easing
            t = t * t * (3.0 - 2.0 * t)  # smoothstep
            
            # Create frame from base image
            frame = base_img.copy()
            frame_draw = ImageDraw.Draw(frame)
            
            # Calculate moving tile position
            from_x = grid_padding + from_col * cell_size + tile_margin
            from_y = grid_padding + from_row * cell_size + tile_margin
            to_x = grid_padding + to_col * cell_size + tile_margin
            to_y = grid_padding + to_row * cell_size + tile_margin
            
            current_x = from_x + (to_x - from_x) * t
            current_y = from_y + (to_y - from_y) * t
            
            # Draw moving tile
            frame_draw.rectangle(
                [current_x, current_y, current_x + tile_size, current_y + tile_size],
                fill=tile_rgb,
                outline=grid_color,
                width=grid_line_width
            )
            
            text = str(tile_value)
            bbox = frame_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = current_x + (tile_size - text_width) / 2
            text_y = current_y + (tile_size - text_height) / 2
            frame_draw.text((text_x, text_y), text, fill='white', font=font)
            
            frames.append(frame)
        
        return frames
        # ══════════════════════════════════════════════════════════════════════════
    #  DATASET GENERATION WITH UNIQUENESS
    # ══════════════════════════════════════════════════════════════════════════
    
    def generate_dataset(self) -> List[TaskPair]:
        """
        Generate complete dataset with uniqueness guarantee.
        
        Supports both single configuration and mixed difficulty distributions.
        """
        # Reset seen_states for deterministic generation
        self.seen_states = set()
        
        pairs = []
        max_retries_per_task = 200
        
        # Check if using difficulty distribution
        if self.config.difficulty_distribution:
            return self._generate_dataset_with_distribution()
        
        # Single configuration generation
        for i in range(self.config.num_samples):
            task_id = f"{self.config.domain}_{i:08d}"
            
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
                print(f"  Generated: {task_id}")
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
        
        return pairs
    
    def _generate_dataset_with_distribution(self) -> List[TaskPair]:
        """
        Generate dataset with mixed difficulty distribution.
        
        Supports different puzzle sizes and move ranges in a single dataset.
        Tasks are generated in random order, not sequentially by difficulty.
        """
        # Reset seen_states for deterministic generation
        self.seen_states = set()
        
        pairs = []
        max_retries_per_task = 200
        
        dist = self.config.difficulty_distribution
        total_weight = sum(d.get("weight", 1.0) for d in dist.values())
        
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
        
        # Distribute remaining samples
        if remaining > 0:
            difficulties = list(difficulty_samples.keys())
            for i in range(remaining):
                difficulty_samples[difficulties[i % len(difficulties)]]["count"] += 1
        
        # Create a shuffled list of task specifications (mixed order)
        task_specs = []
        for difficulty, info in difficulty_samples.items():
            count = info["count"]
            config = info["config"]
            
            size = config["size"]
            min_moves = config["min_moves"]
            max_moves = config["max_moves"]
            method = config.get("generation_method", self.config.generation_method)
            
            # Add count tasks of this difficulty
            for _ in range(count):
                task_specs.append({
                    "size": size,
                    "min_moves": min_moves,
                    "max_moves": max_moves,
                    "generation_method": method,
                    "difficulty": difficulty
                })
        
        # Shuffle the task specs to mix different sizes
        self.rng.shuffle(task_specs)
        
        # Generate tasks in shuffled order
        task_idx = 0
        for spec in task_specs:
            task_id = f"{self.config.domain}_{task_idx:08d}"
            
            pair = self.generate_task_pair(
                task_id,
                max_retries=max_retries_per_task,
                puzzle_size=spec["size"],
                min_moves=spec["min_moves"],
                max_moves=spec["max_moves"],
                generation_method=spec["generation_method"]
            )
            
            if pair is not None:
                pairs.append(pair)
                print(f"  Generated: {task_id}")
                task_idx += 1
            else:
                # Retry with different approach
                for retry in range(5):
                    pair = self.generate_task_pair(
                        task_id,
                        max_retries=50,
                        puzzle_size=spec["size"],
                        min_moves=spec["min_moves"],
                        max_moves=spec["max_moves"],
                        generation_method=spec["generation_method"]
                    )
                    if pair is not None:
                        pairs.append(pair)
                        print(f"  Generated: {task_id}")
                        task_idx += 1
                        break
        
        return pairs

    def _build_objects_metadata(
        self,
        task_data: dict,
        initial_state: List[List[int]],
        goal_state: List[List[int]],
        size: int
    ) -> Dict[str, Any]:
        """
        Build object-centric metadata for sliding puzzle task.
        
        Args:
            task_data: Task data dictionary containing task parameters
            initial_state: Initial puzzle state (2D list)
            goal_state: Goal puzzle state (2D list)
            size: Puzzle size
            
        Returns:
            Dictionary with object-centric metadata
        """
        objects = []
        
        # Find positions for each tile value
        for value in range(1, size * size):  # 1 to (size*size - 1), excluding 0 (blank)
            # Find initial position
            initial_pos = None
            for i in range(size):
                for j in range(size):
                    if initial_state[i][j] == value:
                        initial_pos = [i, j]
                        break
                if initial_pos is not None:
                    break
            
            # Find target position
            target_pos = None
            for i in range(size):
                for j in range(size):
                    if goal_state[i][j] == value:
                        target_pos = [i, j]
                        break
                if target_pos is not None:
                    break
            
            if initial_pos is not None and target_pos is not None:
                objects.append({
                    "symbol": f"tile_{value}",
                    "value": value,
                    "initial_position": initial_pos,
                    "target_position": target_pos,
                    "color": task_data["tile_color_theme"]
                })
        
        # Add blank space object
        blank_initial = None
        blank_target = None
        for i in range(size):
            for j in range(size):
                if initial_state[i][j] == 0:
                    blank_initial = [i, j]
                if goal_state[i][j] == 0:
                    blank_target = [i, j]
                if blank_initial is not None and blank_target is not None:
                    break
            if blank_initial is not None and blank_target is not None:
                break
        
        if blank_initial is not None and blank_target is not None:
            objects.append({
                "symbol": "blank",
                "value": 0,
                "initial_position": blank_initial,
                "target_position": blank_target,
                "color": None
            })
        
        # Build task-specific metadata
        optimized_task_data = {
            "size": task_data["size"],
            "min_moves": task_data["min_moves"],
            "max_moves": task_data["max_moves"],
            "solution_length": task_data["solution_length"],
            "tile_color_theme": task_data["tile_color_theme"],
            "generation_method": task_data["generation_method"],
            "objects": objects
        }
        
        return optimized_task_data
