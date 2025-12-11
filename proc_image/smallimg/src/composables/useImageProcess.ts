import { ref } from "vue";
import type { ProcessOptions, ProcessedImage } from "@/types";
import { calculateCompressionRatio } from "@/utils/image-utils";
import { generateWebPFileName } from "@/utils/file-utils";

// 后端图片压缩 API 基础地址
const API_BASE_URL =
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  import.meta.env.VITE_PDF_API_BASE_URL ||
  "http://localhost:8000";

interface ImageCompressResponseApi {
  success: boolean;
  message: string;
  filename: string;
  output_filename: string;
  download_url: string;
  metadata: {
    original_size: number;
    output_size: number;
    compression_ratio: number;
    original_dimensions: string; // e.g. "3840x2160"
    output_dimensions: string; // e.g. "1920x1080"
    quality: number;
  };
}

export function useImageProcess() {
  const processing = ref(false);
  const progress = ref(0);
  const error = ref<string | null>(null);

  // 用于在等待后端响应时模拟前端进度，避免长时间停留在固定百分比
  let progressTimer: number | null = null;

  const stopProgressTimer = () => {
    if (progressTimer !== null && typeof window !== "undefined") {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
  };

  /**
   * 启动一个假进度条：
   * - 每 200ms 增加 1-2%
   * - 上限为 target（默认 85%），避免在真正结束前显示 100%
   * - 添加随机波动使进度条更自然
   */
  const startProgressTimer = (target = 85) => {
    if (typeof window === "undefined") return;
    stopProgressTimer();
    progressTimer = window.setInterval(() => {
      if (progress.value < target) {
        // 随机增加 1-3%，使进度更自然
        const increment = Math.random() * 2 + 1;
        progress.value = Math.min(target, progress.value + increment);
      } else {
        stopProgressTimer();
      }
    }, 200);
  };

  // 解析形如 "3840x2160" 的尺寸字符串
  const parseDimensions = (dim: string): { width: number; height: number } => {
    const [w, h] = dim.split("x").map((v) => parseInt(v.trim(), 10));
    if (!Number.isFinite(w) || !Number.isFinite(h)) {
      return { width: 0, height: 0 };
    }
    return { width: w, height: h };
  };

  // 调用后端 /api/v1/image/compress 进行图片压缩
  const processImage = async (
    file: File,
    options: ProcessOptions = {}
  ): Promise<ProcessedImage> => {
    processing.value = true;
    progress.value = 0;
    error.value = null;

    try {
      // 第一阶段：准备数据（5% -> 10%）
      progress.value = 5;
      
      const formData = new FormData();
      formData.append("file", file);

      // 将前端选项映射到后端 ImageCompressOptions
      const payloadOptions = {
        quality: options.quality ?? 92,
        max_width: options.maxWidth || 1920,
        max_height: options.maxHeight || 1080,
        // 这里先不启用 target_size_kb，保持简单
      };
      formData.append("options", JSON.stringify(payloadOptions));
      progress.value = 10;

      // 第二阶段：上传和后端处理（10% -> 75%）
      // 启动假进度条模拟后端处理过程
      startProgressTimer(75);

      const resp = await fetch(`${API_BASE_URL}/api/v1/image/compress`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        let detail = "";
        try {
          const data = await resp.json();
          // FastAPI 异常返回 detail 字段
          detail =
            (data?.detail && (data.detail.message || data.detail.details || data.detail)) ||
            JSON.stringify(data);
        } catch {
          detail = resp.statusText;
        }
        throw new Error(`图片压缩失败 (${resp.status}): ${detail}`);
      }

      const data = (await resp.json()) as ImageCompressResponseApi;
      if (!data.success) {
        throw new Error(data.message || "图片压缩失败");
      }

      // 服务端已完成压缩，停止假进度条
      stopProgressTimer();
      progress.value = 76;
      console.log("[useImageProcess] Compression successful, starting download...", data);

      // 下载压缩后的图片二进制，用于预览与本地下载
      const downloadUrl = data.download_url.startsWith("http")
        ? data.download_url
        : `${API_BASE_URL}${data.download_url}`;

      // 第三阶段：下载图片（76% -> 95%）
      // 重试逻辑：最多尝试3次
      let blob: Blob | null = null;
      let lastError: Error | null = null;
      
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          console.log("[useImageProcess] Downloading from", downloadUrl, "attempt:", attempt);
          const imgResp = await fetch(downloadUrl);
          if (!imgResp.ok) {
            lastError = new Error(`下载压缩图片失败 (${imgResp.status}): ${imgResp.statusText}`);
            console.warn("[useImageProcess] Download failed with status", imgResp.status, lastError.message);
            if (attempt < 3) {
              progress.value = 76 + (attempt - 1) * 5;
              await new Promise(resolve => setTimeout(resolve, 500 * attempt));
              continue;
            }
            throw lastError;
          }
          blob = await imgResp.blob();
          console.log("[useImageProcess] Downloaded blob size:", blob.size);
          if (!blob || blob.size === 0) {
            lastError = new Error("下载的文件为空");
            console.warn("[useImageProcess] Blob is empty", blob);
            if (attempt < 3) {
              progress.value = 76 + (attempt - 1) * 5;
              await new Promise(resolve => setTimeout(resolve, 500 * attempt));
              continue;
            }
            throw lastError;
          }
          progress.value = 85;
          console.log("[useImageProcess] Download successful, moving to next step");
          break;
        } catch (e) {
          lastError = e instanceof Error ? e : new Error(String(e));
          console.error("[useImageProcess] Download attempt", attempt, "failed:", lastError.message);
          if (attempt < 3) {
            progress.value = 76 + (attempt - 1) * 5;
            await new Promise(resolve => setTimeout(resolve, 500 * attempt));
          }
        }
      }

      if (!blob || blob.size === 0) {
        const finalError = lastError || new Error("无法下载压缩图片");
        console.error("[useImageProcess] Final download error:", finalError.message);
        throw finalError;
      }

      // 下载完成，进度推进到 95%
      progress.value = 95;
      
      const { original_size, output_size, compression_ratio, original_dimensions, output_dimensions } =
        data.metadata;
      const originalDims = parseDimensions(original_dimensions);
      const outputDims = parseDimensions(output_dimensions);
      
      console.log("[useImageProcess] Creating ProcessedImage object...", {
        blobSize: blob.size,
        originalDims,
        outputDims,
        compression_ratio
      });

      const processedImage: ProcessedImage = {
        blob,
        url: URL.createObjectURL(blob),
        originalFile: file,
        originalSize: original_size || file.size,
        originalWidth: originalDims.width,
        originalHeight: originalDims.height,
        processedSize: output_size,
        processedWidth: outputDims.width,
        processedHeight: outputDims.height,
        compressionRatio:
          typeof compression_ratio === "number"
            ? Math.round(compression_ratio)
            : calculateCompressionRatio(original_size || file.size, output_size),
        fileName: data.output_filename || generateWebPFileName(file.name),
      };

      // 结束时清理定时器并补满到 100%
      stopProgressTimer();
      progress.value = 100;
      processing.value = false;

      return processedImage;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "图片压缩失败";
      error.value = msg;
      processing.value = false;
      stopProgressTimer();
      progress.value = 0;
      throw new Error(msg);
    }
  };

  // 兼容原有 API：目前无需实际清理资源
  const cleanup = () => {
    stopProgressTimer();
  };

  return {
    processing,
    progress,
    error,
    processImage,
    cleanup,
  };
}
