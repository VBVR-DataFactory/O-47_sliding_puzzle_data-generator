#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    LARGE SCALE DATASET GENERATOR                              ║
║                                                                               ║
║  Generate large-scale sliding puzzle datasets with scalable state space      ║
║  Supports generating hundreds or thousands of unique tasks                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    # Generate 1000 tasks with mixed difficulty
    python3 examples/generate_large_dataset.py --num-samples 1000
    
    # Generate 5000 tasks (large scale)
    python3 examples/generate_large_dataset.py --num-samples 5000 --no-videos
    
    # Custom output directory
    python3 examples/generate_large_dataset.py --num-samples 2000 --output data/large_dataset
"""

import argparse
import sys
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import OutputWriter
from src import TaskGenerator, TaskConfig


def create_mixed_config(num_samples: int, generate_videos: bool = False) -> TaskConfig:
    """
    Create a mixed difficulty configuration for large-scale generation.
    
    This configuration generates tasks with different puzzle sizes and move ranges
    to maximize state space and diversity.
    """
    return TaskConfig(
        num_samples=num_samples,
        random_seed=42,  # For reproducibility
        output_dir=Path("data/questions"),
        generate_videos=generate_videos,
        difficulty_distribution={
            'easy': {
                'size': 3,
                'min_moves': 3,
                'max_moves': 6,
                'weight': 0.2,
                'generation_method': 'random'
            },
            'medium': {
                'size': 4,
                'min_moves': 5,
                'max_moves': 10,
                'weight': 0.5,
                'generation_method': 'random'
            },
            'hard': {
                'size': 5,
                'min_moves': 8,
                'max_moves': 15,
                'weight': 0.3,
                'generation_method': 'random'
            }
        }
    )


def create_single_config(
    num_samples: int,
    puzzle_size: int = 4,
    min_moves: int = 5,
    max_moves: int = 12,
    generate_videos: bool = False
) -> TaskConfig:
    """
    Create a single configuration for focused generation.
    
    Best for generating many tasks of the same type.
    """
    return TaskConfig(
        num_samples=num_samples,
        random_seed=42,
        output_dir=Path("data/questions"),
        puzzle_size=puzzle_size,
        min_moves=min_moves,
        max_moves=max_moves,
        generation_method='random',  # Use random for large state space
        generate_videos=generate_videos,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate large-scale sliding puzzle datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate 1000 tasks with mixed difficulty (recommended)
    python3 examples/generate_large_dataset.py --num-samples 1000
    
    # Generate 5000 tasks, single size (4×4)
    python3 examples/generate_large_dataset.py --num-samples 5000 --size 4 --no-videos
    
    # Generate 2000 tasks with custom move range
    python3 examples/generate_large_dataset.py --num-samples 2000 --min-moves 8 --max-moves 15
    
    # Generate with mixed difficulty and custom output
    python3 examples/generate_large_dataset.py --num-samples 3000 --mixed --output data/my_dataset
        """
    )
    
    parser.add_argument(
        "--num-samples",
        type=int,
        required=True,
        help="Number of task samples to generate (can be 1000+)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="data/questions",
        help="Output directory (default: data/questions)"
    )
    
    parser.add_argument(
        "--mixed",
        action="store_true",
        help="Use mixed difficulty distribution (recommended for large datasets)"
    )
    
    parser.add_argument(
        "--size",
        type=int,
        choices=[3, 4, 5],
        default=4,
        help="Puzzle size when not using mixed mode (default: 4)"
    )
    
    parser.add_argument(
        "--min-moves",
        type=int,
        default=5,
        help="Minimum number of moves (default: 5)"
    )
    
    parser.add_argument(
        "--max-moves",
        type=int,
        default=12,
        help="Maximum number of moves (default: 12, can go up to 20)"
    )
    
    parser.add_argument(
        "--no-videos",
        action="store_true",
        help="Disable video generation (recommended for large datasets)"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🧩 LARGE SCALE SLIDING PUZZLE DATASET GENERATOR")
    print("=" * 70)
    print(f"\n📊 Configuration:")
    print(f"   Total samples: {args.num_samples:,}")
    print(f"   Output directory: {args.output}")
    print(f"   Videos: {'Disabled' if args.no_videos else 'Enabled'}")
    
    # Create configuration
    if args.mixed:
        print(f"   Mode: Mixed difficulty (3×3, 4×4, 5×5)")
        config = create_mixed_config(args.num_samples, generate_videos=not args.no_videos)
    else:
        print(f"   Mode: Single size ({args.size}×{args.size})")
        print(f"   Moves range: {args.min_moves}-{args.max_moves}")
        config = create_single_config(
            args.num_samples,
            puzzle_size=args.size,
            min_moves=args.min_moves,
            max_moves=args.max_moves,
            generate_videos=not args.no_videos
        )
    
    config.random_seed = args.seed
    config.output_dir = Path(args.output)
    
    print(f"\n🚀 Starting generation...")
    print(f"   This may take a while for large datasets...\n")
    
    # Record start time
    start_time = time.time()
    
    # Generate tasks
    generator = TaskGenerator(config)
    tasks = generator.generate_dataset()
    
    # Record end time
    elapsed_time = time.time() - start_time
    
    # Write to disk
    print(f"\n💾 Writing tasks to disk...")
    writer = OutputWriter(Path(args.output))
    writer.write_dataset(tasks)
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ GENERATION COMPLETE")
    print("=" * 70)
    print(f"\n📈 Statistics:")
    print(f"   Requested: {args.num_samples:,} tasks")
    print(f"   Generated: {len(tasks):,} unique tasks")
    print(f"   Success rate: {len(tasks)/args.num_samples*100:.1f}%")
    print(f"   Unique states: {len(generator.seen_states):,}")
    print(f"   Generation time: {elapsed_time:.2f} seconds")
    print(f"   Average speed: {len(tasks)/elapsed_time:.1f} tasks/second")
    
    if args.no_videos:
        print(f"   (Videos disabled for faster generation)")
    
    print(f"\n📁 Output location:")
    print(f"   {args.output}/{config.domain}_task/")
    print(f"   ({len(tasks)} task folders)")
    
    if len(tasks) < args.num_samples:
        print(f"\n⚠️  Warning: Generated {len(tasks)}/{args.num_samples} tasks")
        print(f"   Consider:")
        print(f"   - Increasing max_moves (current: {args.max_moves})")
        print(f"   - Using --mixed mode for more diversity")
        print(f"   - Using larger puzzle size (4×4 or 5×5)")
    else:
        print(f"\n🎉 Successfully generated all {len(tasks):,} unique tasks!")
    
    print("=" * 70)


if __name__ == "__main__":
    main()

