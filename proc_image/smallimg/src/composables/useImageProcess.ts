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
    progress.value = 5;
    error.value = null;

    try {
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

      progress.value = 20;

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

      progress.value = 60;

      // 下载压缩后的图片二进制，用于预览与本地下载
      const downloadUrl = data.download_url.startsWith("http")
        ? data.download_url
        : `${API_BASE_URL}${data.download_url}`;

      const imgResp = await fetch(downloadUrl);
      if (!imgResp.ok) {
        throw new Error(`下载压缩图片失败 (${imgResp.status})`);
      }

      const blob = await imgResp.blob();

      const { original_size, output_size, compression_ratio, original_dimensions, output_dimensions } =
        data.metadata;
      const originalDims = parseDimensions(original_dimensions);
      const outputDims = parseDimensions(output_dimensions);

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

      progress.value = 100;
      processing.value = false;

      return processedImage;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "图片压缩失败";
      error.value = msg;
      processing.value = false;
      progress.value = 0;
      throw new Error(msg);
    }
  };

  // 兼容原有 API：目前无需实际清理资源
  const cleanup = () => {
    // no-op
  };

  return {
    processing,
    progress,
    error,
    processImage,
    cleanup,
  };
}
