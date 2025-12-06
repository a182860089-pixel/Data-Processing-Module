// 处理选项
export interface ProcessOptions {
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

// 处理后的图片信息
export interface ProcessedImage {
  blob: Blob;
  url: string;
  originalFile: File;
  originalSize: number;
  originalWidth: number;
  originalHeight: number;
  processedSize: number;
  processedWidth: number;
  processedHeight: number;
  compressionRatio: number;
  fileName: string;
}

// 处理状态
export type ProcessStatus = "pending" | "processing" | "completed" | "failed";

// 图片项
export interface ImageItem {
  id: string;
  file: File;
  status: ProcessStatus;
  progress: number;
  error?: string;
  result?: ProcessedImage;
}

// Worker 消息类型
export interface WorkerMessage {
  type: "progress" | "success" | "error";
  progress?: number;
  result?: {
    blob: Blob;
    width: number;
    height: number;
    size: number;
  };
  error?: string;
}

// Worker 请求
export interface WorkerRequest {
  file: File;
  options: ProcessOptions;
}
