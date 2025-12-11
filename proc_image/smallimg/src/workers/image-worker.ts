import Pica from "pica";
import { encode } from "@jsquash/webp";

// 计算目标尺寸
function calculateTargetSize(originalWidth: number, originalHeight: number, maxWidth: number = 1920, maxHeight: number = 1080): { width: number; height: number } {
  if (originalWidth <= maxWidth && originalHeight <= maxHeight) {
    return { width: originalWidth, height: originalHeight };
  }

  const widthRatio = maxWidth / originalWidth;
  const heightRatio = maxHeight / originalHeight;
  const ratio = Math.min(widthRatio, heightRatio);

  const width = Math.floor(originalWidth * ratio);
  const height = Math.floor(originalHeight * ratio);

  return { width, height };
}

// 处理图片
async function processImage(
  file: File,
  options: {
    maxWidth?: number;
    maxHeight?: number;
    quality?: number;
    method?: number;
    pass?: number;
    use_sharp_yuv?: number;
    sns_strength?: number;
    filter_strength?: number;
    filter_sharpness?: number;
  }
): Promise<{
  blob: Blob;
  width: number;
  height: number;
  size: number;
}> {
  const { maxWidth = 1920, maxHeight = 1080, quality = 92, method = 6, pass = 8, use_sharp_yuv = 1, sns_strength = 75, filter_strength = 30, filter_sharpness = 3 } = options;

  try {
    // 发送进度: 20% - 开始读取文件
    self.postMessage({ type: "progress", progress: 20 });

    // 读取文件为ArrayBuffer
    const arrayBuffer = await file.arrayBuffer();

    // 发送进度: 40% - 解码图片
    self.postMessage({ type: "progress", progress: 40 });

    // 创建ImageBitmap
    const blob = new Blob([arrayBuffer], { type: file.type });
    const imageBitmap = await createImageBitmap(blob);

    const originalWidth = imageBitmap.width;
    const originalHeight = imageBitmap.height;

    // 计算目标尺寸
    const targetSize = calculateTargetSize(originalWidth, originalHeight, maxWidth, maxHeight);

    // 发送进度: 50% - 开始缩放
    self.postMessage({ type: "progress", progress: 50 });

    // 创建源canvas
    const sourceCanvas = new OffscreenCanvas(originalWidth, originalHeight);
    const sourceCtx = sourceCanvas.getContext("2d");
    if (!sourceCtx) {
      throw new Error("无法创建源canvas上下文");
    }
    sourceCtx.drawImage(imageBitmap, 0, 0);

    // 创建目标canvas
    const targetCanvas = new OffscreenCanvas(targetSize.width, targetSize.height);

    // 使用pica进行高质量缩放（若失败则回退到原生 drawImage）
    try {
      const pica = new Pica();
      await pica.resize(sourceCanvas, targetCanvas, {
        quality: 3, // 最高质量 (LANCZOS)
        alpha: true,
        unsharpAmount: 120,
        unsharpRadius: 1.2,
        unsharpThreshold: 10,
      });
    } catch (e) {
      // 回退：使用 2D drawImage 进行缩放，避免某些环境禁用 getImageData 导致 Pica 报错
      const tctx = targetCanvas.getContext("2d");
      if (!tctx) {
        throw new Error("无法创建目标canvas上下文");
      }
      tctx.imageSmoothingEnabled = true;
      // @ts-ignore
      tctx.imageSmoothingQuality = "high";
      tctx.drawImage(sourceCanvas as any, 0, 0, originalWidth, originalHeight, 0, 0, targetSize.width, targetSize.height);
    }

    // 发送进度: 70% - 开始编码
    self.postMessage({ type: "progress", progress: 70 });

    // 获取ImageData；若被浏览器保护禁止，则回退到 convertToBlob
    const ctx = targetCanvas.getContext("2d");
    if (!ctx) {
      throw new Error("无法创建目标canvas上下文");
    }

    let resultBlob: Blob;
    try {
      const imageData = ctx.getImageData(0, 0, targetSize.width, targetSize.height);
      // 发送进度: 90% - WebP编码
      self.postMessage({ type: "progress", progress: 90 });
      const webpData = await encode(imageData, { quality, method, pass, use_sharp_yuv, sns_strength, filter_strength, filter_sharpness });
      resultBlob = new Blob([webpData], { type: "image/webp" });
    } catch (e) {
      // 某些环境（反指纹/扩展）会禁止 getImageData，这里使用浏览器内建编码
      const q = Math.max(0, Math.min(1, quality / 100));
      // @ts-ignore OffscreenCanvas
      if (typeof (targetCanvas as any).convertToBlob === "function") {
        // @ts-ignore
        resultBlob = await (targetCanvas as any).convertToBlob({ type: "image/webp", quality: q });
      } else {
        // 兼容 HTMLCanvasElement（一般不会在 worker 中出现）
        const canvasEl = targetCanvas as unknown as HTMLCanvasElement;
        resultBlob = await new Promise<Blob>((resolve, reject) => {
          canvasEl.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob 失败"))), "image/webp", q);
        });
      }
    }

    // 发送进度: 100% - 完成
    self.postMessage({ type: "progress", progress: 100 });

    return {
      blob: resultBlob,
      width: targetSize.width,
      height: targetSize.height,
      size: resultBlob.size,
    };
  } catch (error) {
    throw new Error(`图片处理失败: ${error instanceof Error ? error.message : "未知错误"}`);
  }
}

// 监听消息
self.onmessage = async (e: MessageEvent) => {
  const { file, options } = e.data;

  try {
    const result = await processImage(file, options);
    self.postMessage({
      type: "success",
      result,
    });
  } catch (error) {
    self.postMessage({
      type: "error",
      error: error instanceof Error ? error.message : "未知错误",
    });
  }
};
