#!/usr/bin/env python3
"""
生成50个滑动拼图任务，包含ground truth video

用于测试和验证数据质量
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import OutputWriter
from src import TaskGenerator, TaskConfig


def main():
    print("=" * 70)
    print("🧩 生成50个滑动拼图任务（包含ground truth video）")
    print("=" * 70)
    
    # 配置：生成50个任务，启用视频
    config = TaskConfig(
        num_samples=50,
        puzzle_size=4,  # 使用4×4拼图，状态空间更大
        min_moves=5,
        max_moves=10,
        generation_method='random',  # 使用随机生成，状态空间大
        generate_videos=True,  # ✅ 启用视频生成
        video_fps=10,
        output_dir=Path("data/questions"),
        random_seed=42
    )
    
    print(f"\n📊 配置信息:")
    print(f"   任务数量: {config.num_samples}")
    print(f"   拼图大小: {config.puzzle_size}×{config.puzzle_size}")
    print(f"   步数范围: {config.min_moves}-{config.max_moves}")
    print(f"   生成方法: {config.generation_method}")
    print(f"   视频生成: {'启用' if config.generate_videos else '禁用'}")
    print(f"   输出目录: {config.output_dir}")
    
    print(f"\n🚀 开始生成...\n")
    
    # 生成任务
    generator = TaskGenerator(config)
    tasks = generator.generate_dataset()
    
    # 写入磁盘
    print(f"\n💾 写入文件...")
    writer = OutputWriter(config.output_dir)
    writer.write_dataset(tasks)
    
    # 统计信息
    print(f"\n" + "=" * 70)
    print(f"✅ 生成完成！")
    print(f"=" * 70)
    print(f"\n📈 统计:")
    print(f"   生成任务数: {len(tasks)}")
    print(f"   唯一状态数: {len(generator.seen_states)}")
    print(f"   成功率: {len(tasks)/config.num_samples*100:.1f}%")
    
    # 检查视频文件
    output_path = config.output_dir / f"{config.domain}_task"
    video_count = 0
    if output_path.exists():
        for task_dir in output_path.iterdir():
            if task_dir.is_dir():
                video_file = task_dir / "ground_truth.mp4"
                if video_file.exists():
                    video_count += 1
    
    print(f"   包含视频的任务: {video_count}/{len(tasks)}")
    
    print(f"\n📁 输出位置:")
    print(f"   {output_path}")
    print(f"\n每个任务包含:")
    print(f"   - first_frame.png (初始状态)")
    print(f"   - final_frame.png (目标状态)")
    print(f"   - prompt.txt (任务提示)")
    print(f"   - ground_truth.mp4 (解决方案视频)")
    print(f"=" * 70)


if __name__ == "__main__":
    main()

