#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片批量压缩脚本 - 组合2：极致压缩版本

功能：
1. 图片尺寸向下采样，长宽不超过 1920×1080
2. 极致压缩（质量80）
3. 删除图片元数据
4. 转换为 WebP 格式

组合2优化：
- quality=80：较低质量，体积更小
- minimize_size=True：自动优化编码方式
- pass=10：多次压缩迭代优化
- 预期体积减少：35-45%
- CPU消耗增加：100-150%
"""

import os
import sys
from pathlib import Path
from PIL import Image
import argparse


# 支持的输入图片格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}

# 最大尺寸限制
MAX_WIDTH = 1920
MAX_HEIGHT = 1080

# WebP 质量参数（组合2：极致压缩）
WEBP_QUALITY = 95

# 组合2：极致压缩优化参数
USE_MINIMIZE_SIZE = True  # 自动优化编码方式
COMPRESSION_PASSES = 1  # 压缩迭代次数（1-10，越高越慢但体积越小）


def get_new_dimensions(width, height, max_width=MAX_WIDTH, max_height=MAX_HEIGHT):
    """
    计算新的图片尺寸，保持宽高比
    
    Args:
        width: 原始宽度
        height: 原始高度
        max_width: 最大宽度
        max_height: 最大高度
    
    Returns:
        (new_width, new_height): 新的宽度和高度
    """
    # 如果图片已经在限制范围内，不需要缩放
    if width <= max_width and height <= max_height:
        return width, height
    
    # 计算宽度和高度的缩放比例
    width_ratio = max_width / width
    height_ratio = max_height / height
    
    # 选择较小的比例，确保两个维度都不超过限制
    scale_ratio = min(width_ratio, height_ratio)
    
    # 计算新尺寸
    new_width = int(width * scale_ratio)
    new_height = int(height * scale_ratio)
    
    return new_width, new_height


def compress_image(input_path, output_path, quality=WEBP_QUALITY):
    """
    压缩单张图片
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        quality: WebP 质量参数 (0-100)
    
    Returns:
        bool: 是否成功
    """
    try:
        # 打开图片
        with Image.open(input_path) as img:
            # 转换为 RGB 模式（WebP 需要）
            # 如果是 RGBA 或 P 模式，需要特殊处理
            if img.mode in ('RGBA', 'LA', 'PA'):
                # 保留透明通道
                img = img.convert('RGBA')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 获取原始尺寸
            original_width, original_height = img.size
            
            # 计算新尺寸
            new_width, new_height = get_new_dimensions(original_width, original_height)
            
            # 如果需要缩放
            if (new_width, new_height) != (original_width, original_height):
                # 使用 LANCZOS 重采样算法，保证高质量
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"  缩放: {original_width}×{original_height} → {new_width}×{new_height}")
            else:
                print(f"  尺寸: {original_width}×{original_height} (无需缩放)")
            
            # 【组合2】保存为 WebP 格式（极致压缩参数）
            # method=6: 使用最高质量的压缩方法（速度较慢但效果最好）
            # minimize_size=True: 自动尝试多种编码方式，选择最小的
            # pass=10: 多次压缩迭代优化
            # lossless=False: 有损压缩
            save_params = {
                'format': 'WEBP',
                'quality': quality,
                'method': 6,
                'lossless': False
            }

            # 添加组合2的优化参数
            if USE_MINIMIZE_SIZE:
                save_params['minimize_size'] = True
                print(f"  启用 minimize_size 优化")

            # 注意：Pillow 的 WebP 编码器可能不支持 pass 参数
            # 如果支持，添加 pass 参数
            try:
                # 尝试添加 pass 参数
                save_params_with_pass = save_params.copy()
                save_params_with_pass['pass'] = COMPRESSION_PASSES

                print(f"  保存参数: quality={quality}, method=6, minimize_size=True, pass={COMPRESSION_PASSES}")
                img.save(output_path, **save_params_with_pass)
            except (TypeError, ValueError):
                # 如果不支持 pass 参数，使用基础参数
                print(f"  保存参数: quality={quality}, method=6, minimize_size=True (pass 参数不支持)")
                img.save(output_path, **save_params)
            
            return True
            
    except Exception as e:
        print(f"  ❌ 错误: {str(e)}")
        return False


def process_folder(folder_path, output_folder=None, quality=WEBP_QUALITY):
    """
    处理文件夹中的所有图片
    
    Args:
        folder_path: 输入文件夹路径
        output_folder: 输出文件夹路径（如果为 None，则保存在原文件夹）
        quality: WebP 质量参数
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"❌ 错误: 文件夹不存在: {folder_path}")
        return
    
    if not folder_path.is_dir():
        print(f"❌ 错误: 不是一个文件夹: {folder_path}")
        return
    
    # 如果没有指定输出文件夹，使用原文件夹
    if output_folder is None:
        output_folder = folder_path
    else:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    # 查找所有支持的图片文件
    image_files = []
    for ext in SUPPORTED_FORMATS:
        image_files.extend(folder_path.glob(f'*{ext}'))
        image_files.extend(folder_path.glob(f'*{ext.upper()}'))
    
    if not image_files:
        print(f"⚠️  警告: 在文件夹中没有找到支持的图片文件")
        print(f"支持的格式: {', '.join(SUPPORTED_FORMATS)}")
        return
    
    print(f"\n📁 处理文件夹: {folder_path}")
    print(f"📁 输出文件夹: {output_folder}")
    print(f"🖼️  找到 {len(image_files)} 张图片\n")
    
    success_count = 0
    fail_count = 0
    total_original_size = 0
    total_compressed_size = 0
    
    for i, image_file in enumerate(image_files, 1):
        # 获取原始文件大小
        original_size = image_file.stat().st_size
        total_original_size += original_size
        
        # 生成输出文件名
        output_filename = image_file.stem + '_compressed.webp'
        output_path = output_folder / output_filename
        
        print(f"[{i}/{len(image_files)}] 处理: {image_file.name}")
        print(f"  原始大小: {original_size / 1024:.2f} KB")
        
        # 压缩图片
        if compress_image(image_file, output_path, quality):
            compressed_size = output_path.stat().st_size
            total_compressed_size += compressed_size
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            print(f"  压缩后: {compressed_size / 1024:.2f} KB")
            print(f"  压缩率: {compression_ratio:.1f}%")
            print(f"  ✅ 保存到: {output_path.name}\n")
            success_count += 1
        else:
            fail_count += 1
            print()
    
    # 打印统计信息
    print("=" * 60)
    print(f"✅ 成功: {success_count} 张")
    print(f"❌ 失败: {fail_count} 张")
    print(f"📊 总原始大小: {total_original_size / 1024 / 1024:.2f} MB")
    print(f"📊 总压缩后大小: {total_compressed_size / 1024 / 1024:.2f} MB")
    if total_original_size > 0:
        total_compression_ratio = (1 - total_compressed_size / total_original_size) * 100
        print(f"📊 总体压缩率: {total_compression_ratio:.1f}%")
    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='批量压缩图片并转换为 WebP 格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python compress_images.py
  python compress_images.py -q 80
  python compress_images.py -o ./output
        """
    )
    
    parser.add_argument(
        '-q', '--quality',
        type=int,
        default=WEBP_QUALITY,
        help=f'WebP 质量参数 (0-100)，默认: {WEBP_QUALITY}'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出文件夹路径（默认: 与输入文件夹相同）'
    )
    
    args = parser.parse_args()
    
    # 验证质量参数
    if not 0 <= args.quality <= 100:
        print("❌ 错误: 质量参数必须在 0-100 之间")
        sys.exit(1)
    
    # 获取用户输入的文件夹路径
    print("=" * 60)
    print("图片批量压缩工具")
    print("=" * 60)
    folder_path = input("\n请输入要处理的文件夹路径: ").strip()
    
    # 移除可能的引号
    folder_path = folder_path.strip('"').strip("'")
    
    if not folder_path:
        print("❌ 错误: 文件夹路径不能为空")
        sys.exit(1)
    
    # 处理文件夹
    process_folder(folder_path, args.output, args.quality)


if __name__ == '__main__':
    main()

