import argparse
import os
import sys
from pathlib import Path

try:
    import pyvips
except Exception as e:
    print("[ERROR] 需要安装 pyvips: pip install pyvips\n错误信息:", e, file=sys.stderr)
    sys.exit(1)

# 允许的输入图片扩展名（大小写不敏感）
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".heif",
    ".gif"  # 将尽量处理静态 gif，动图将被跳过
}


def is_animated(image: pyvips.Image) -> bool:
    # n_pages > 1 通常表示多页图（动图/多帧/多层）
    try:
        return int(getattr(image, 'n_pages', 1)) > 1
    except Exception:
        return False


def ensure_srgb(image: pyvips.Image) -> pyvips.Image:
    try:
        if image.interpretation != pyvips.Interpretation.srgb:
            return image.colourspace(pyvips.Interpretation.srgb)
    except Exception:
        # 一些格式不支持/无 ICC，直接返回
        pass
    return image


def maybe_autorotate(image: pyvips.Image) -> pyvips.Image:
    """
    尝试依据 EXIF 方向对图像进行物理旋转；不同版本返回签名可能不同，这里做兼容处理。
    """
    try:
        res = image.autorot()
        if isinstance(res, pyvips.Image):
            return res
        # 某些版本可能返回 (image, angle) 或 (image, angle, flip)
        if isinstance(res, (tuple, list)) and len(res) >= 1 and isinstance(res[0], pyvips.Image):
            return res[0]
    except Exception:
        pass
    return image



def resize_to_box(image: pyvips.Image, max_w: int, max_h: int) -> pyvips.Image:
    # 保持比例缩放到不超过 max_w x max_h
    width, height = image.width, image.height
    if width <= max_w and height <= max_h:
        return image
    scale = min(max_w / width, max_h / height)
    # 大幅缩小时，先整数缩小再连续缩放，质量和性能更好
    try:
        shrink = max(1, int(1 // scale))  # 1/scale 的整数部分
        if shrink > 1:
            image = image.shrink(shrink, shrink)
            # 剩余比例
            width, height = image.width, image.height
            scale = min(max_w / width, max_h / height)
    except Exception:
        # 某些格式可能不支持 shrink，退回到一次性 resize
        pass
    return image.resize(scale, kernel=pyvips.Kernel.LANCZOS3)


def save_webp(image: pyvips.Image, out_path: str, quality: int) -> None:
    # 去除元数据尽量使用 strip 选项；如遇老版本不支持则自动降级
    # 同时尽量选择高质量有损压缩（非 lossless）
    tried = []
    # 优先尝试 write_to_file，兼容性最好
    try:
        image.write_to_file(out_path, Q=quality, strip=True)
        return
    except Exception as e:
        tried.append(("write_to_file(strip=True)", str(e)))
    # 尝试 webpsave + strip
    try:
        image.webpsave(out_path, Q=quality, strip=True)
        return
    except Exception as e:
        tried.append(("webpsave(strip=True)", str(e)))
    # 去掉 strip 兜底（仍是有损压缩，但可能会保留元数据；一般多数输入本就少元数据）
    try:
        image.write_to_file(out_path, Q=quality)
        return
    except Exception as e:
        tried.append(("write_to_file(no-strip)", str(e)))
    # 最后一次兜底
    image.webpsave(out_path, Q=quality)


def process_one(in_path: Path, out_path: Path, max_w: int, max_h: int, quality: int, overwrite: bool) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not overwrite:
        # 已存在则跳过
        return True

    # 顺序读有助于大图性能
    image = pyvips.Image.new_from_file(str(in_path), access="sequential")

    # 跳过动图等多页图
    if is_animated(image):
        print(f"[SKIP] 多帧/动图跳过: {in_path}")
        return False

    # 依据 EXIF 方向自动旋转一次（去元数据前防止旋转信息丢失）
    image = maybe_autorotate(image)

    # 转 sRGB（去 ICC 前防止出现色偏）
    image = ensure_srgb(image)

    # 缩放至不超过 1920x1080（可调）
    image = resize_to_box(image, max_w, max_h)

    # 保存为 webp（有损压缩），去元数据
    save_webp(image, str(out_path), quality)

    print(f"[OK] {in_path} -> {out_path}")
    return True


def should_process(file: Path) -> bool:
    return file.is_file() and file.suffix.lower() in IMAGE_EXTS


def main():
    parser = argparse.ArgumentParser(description="使用 pyvips 将图片批量转换为高质量有损 WebP（限制大小、去元数据）")
    parser.add_argument("input_dir", nargs="?", default=r"D:\\coding\\proc_image\\testimgs",
                        help="待处理的图片文件夹（默认: D:/coding/proc_image/testimgs）")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="输出文件夹（默认: 在输入目录下创建 webp_output）")
    parser.add_argument("--max-width", type=int, default=1920, help="最大宽度（默认: 1920）")
    parser.add_argument("--max-height", type=int, default=1080, help="最大高度（默认: 1080）")
    parser.add_argument("--quality", "-q", type=int, default=90, help="WebP 质量 0-100（默认: 85）")
    parser.add_argument("--recurse", action="store_true", help="递归处理子目录（默认: 否）")
    parser.add_argument("--overwrite", action="store_true", help="如目标已存在则覆盖（默认: 否）")

    args = parser.parse_args()

    in_dir = Path(args.input_dir).resolve()
    if not in_dir.exists() or not in_dir.is_dir():
        print(f"[ERROR] 输入目录不存在或不是目录: {in_dir}", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.output_dir).resolve() if args.output_dir else in_dir / "webp_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 收集文件
    files = []
    if args.recurse:
        for p in in_dir.rglob("*"):
            if should_process(p):
                files.append(p)
    else:
        for p in in_dir.iterdir():
            if should_process(p):
                files.append(p)

    if not files:
        print("[INFO] 未找到可处理的图片文件。")
        sys.exit(0)

    total = 0
    ok = 0
    for f in files:
        rel = f.relative_to(in_dir)
        # 输出路径同名改为 .webp
        dest = out_dir / rel
        dest = dest.with_suffix('.webp')
        try:
            if process_one(f, dest, args.max_width, args.max_height, args.quality, args.overwrite):
                ok += 1
        except Exception as e:
            print(f"[FAIL] 处理失败: {f} -> {e}")
        total += 1

    print(f"完成: 成功 {ok}/{total}，输出目录: {out_dir}")


if __name__ == "__main__":
    main()

