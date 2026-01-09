#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CUSTOM DATASET GENERATOR (Python API)                      ║
║                                                                               ║
║  Example code for generating datasets programmatically                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

This script shows how to use the TaskGenerator API directly in Python code.
Use this when you need custom logic or want to integrate into your own pipeline.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import OutputWriter
from src import TaskGenerator, TaskConfig


def example_1_single_config():
    """Example 1: Generate 1000 tasks with single configuration"""
    print("=" * 70)
    print("Example 1: Single Configuration (1000 tasks, 4×4)")
    print("=" * 70)
    
    config = TaskConfig(
        num_samples=1000,
        puzzle_size=4,
        min_moves=5,
        max_moves=12,
        generation_method='random',  # Use random for large state space
        generate_videos=False,  # Disable videos for faster generation
        output_dir=Path("data/questions"),
        random_seed=42
    )
    
    generator = TaskGenerator(config)
    tasks = generator.generate_dataset()
    
    # Write to disk
    writer = OutputWriter(config.output_dir)
    writer.write_dataset(tasks)
    
    print(f"✅ Generated {len(tasks)} unique tasks")
    print(f"   Unique states: {len(generator.seen_states)}")
    print(f"   Output: {config.output_dir}/{config.domain}_task/\n")


def example_2_mixed_difficulty():
    """Example 2: Generate 2000 tasks with mixed difficulty"""
    print("=" * 70)
    print("Example 2: Mixed Difficulty (2000 tasks)")
    print("=" * 70)
    
    config = TaskConfig(
        num_samples=2000,
        generate_videos=False,
        output_dir=Path("data/questions"),
        random_seed=42,
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
    
    generator = TaskGenerator(config)
    tasks = generator.generate_dataset()
    
    # Write to disk
    writer = OutputWriter(config.output_dir)
    writer.write_dataset(tasks)
    
    print(f"✅ Generated {len(tasks)} unique tasks")
    print(f"   Unique states: {len(generator.seen_states)}")
    print(f"   Output: {config.output_dir}/{config.domain}_task/\n")


def example_3_large_scale():
    """Example 3: Generate 5000 tasks for large-scale dataset"""
    print("=" * 70)
    print("Example 3: Large Scale (5000 tasks, 5×5)")
    print("=" * 70)
    
    config = TaskConfig(
        num_samples=5000,
        puzzle_size=5,  # Larger puzzle for more state space
        min_moves=8,
        max_moves=18,  # Larger move range
        generation_method='random',
        generate_videos=False,
        output_dir=Path("data/large_dataset"),
        random_seed=42
    )
    
    generator = TaskGenerator(config)
    tasks = generator.generate_dataset()
    
    # Write to disk
    writer = OutputWriter(config.output_dir)
    writer.write_dataset(tasks)
    
    print(f"✅ Generated {len(tasks)} unique tasks")
    print(f"   Unique states: {len(generator.seen_states)}")
    print(f"   Output: {config.output_dir}/{config.domain}_task/\n")


def example_4_custom_batch():
    """Example 4: Generate multiple batches with different configs"""
    print("=" * 70)
    print("Example 4: Custom Batch Generation")
    print("=" * 70)
    
    # Define different batches
    batches = [
        {'size': 3, 'samples': 500, 'min_moves': 3, 'max_moves': 6},
        {'size': 4, 'samples': 1000, 'min_moves': 5, 'max_moves': 10},
        {'size': 5, 'samples': 500, 'min_moves': 8, 'max_moves': 15},
    ]
    
    all_tasks = []
    total_states = set()
    
    for i, batch in enumerate(batches):
        print(f"\nBatch {i+1}: {batch['samples']} tasks, {batch['size']}×{batch['size']}")
        
        config = TaskConfig(
            num_samples=batch['samples'],
            puzzle_size=batch['size'],
            min_moves=batch['min_moves'],
            max_moves=batch['max_moves'],
            generation_method='random',
            generate_videos=False,
            output_dir=Path("data/custom_batch"),
            random_seed=42 + i  # Different seed for each batch
        )
        
        generator = TaskGenerator(config)
        tasks = generator.generate_dataset()
        all_tasks.extend(tasks)
        total_states.update(generator.seen_states)
        
        print(f"  ✅ Generated {len(tasks)} tasks")
    
    # Write all tasks
    writer = OutputWriter(Path("data/custom_batch"))
    writer.write_dataset(all_tasks)
    
    print(f"\n✅ Total: {len(all_tasks)} unique tasks")
    print(f"   Total unique states: {len(total_states)}")
    print(f"   Output: data/custom_batch/{config.domain}_task/\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run example dataset generation")
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="Which example to run (default: 1)"
    )
    
    args = parser.parse_args()
    
    examples = {
        1: example_1_single_config,
        2: example_2_mixed_difficulty,
        3: example_3_large_scale,
        4: example_4_custom_batch,
    }
    
    examples[args.example]()

