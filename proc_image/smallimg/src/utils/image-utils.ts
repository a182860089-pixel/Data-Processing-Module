/**
 * 计算目标尺寸
 * @param originalWidth 原始宽度
 * @param originalHeight 原始高度
 * @param maxWidth 最大宽度
 * @param maxHeight 最大高度
 * @returns 目标尺寸 {width, height}
 */
export function calculateTargetSize(originalWidth: number, originalHeight: number, maxWidth: number = 1920, maxHeight: number = 1080): { width: number; height: number } {
  // 如果图片已在限制范围内，不进行缩放
  if (originalWidth <= maxWidth && originalHeight <= maxHeight) {
    return { width: originalWidth, height: originalHeight };
  }

  // 计算宽度和高度的缩放比例
  const widthRatio = maxWidth / originalWidth;
  const heightRatio = maxHeight / originalHeight;

  // 取较小值，确保两个维度都不超过限制
  const ratio = Math.min(widthRatio, heightRatio);

  // 计算新尺寸，向下取整
  const width = Math.floor(originalWidth * ratio);
  const height = Math.floor(originalHeight * ratio);

  return { width, height };
}

/**
 * 格式化文件大小
 * @param bytes 字节数
 * @returns 格式化后的字符串
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

/**
 * 计算压缩率
 * @param originalSize 原始大小
 * @param compressedSize 压缩后大小
 * @returns 压缩率百分比
 */
export function calculateCompressionRatio(originalSize: number, compressedSize: number): number {
  if (originalSize === 0) return 0;
  return Math.round(((originalSize - compressedSize) / originalSize) * 100);
}

/**
 * 验证文件类型
 * @param file 文件对象
 * @returns 是否为有效的图片文件
 */
export function isValidImageFile(file: File): boolean {
  const validTypes = [
    "image/jpeg",
    "image/jpg", // 某些系统使用 image/jpg
    "image/png",
    "image/bmp",
    "image/gif",
    "image/tiff",
    "image/webp",
  ];
  return validTypes.includes(file.type);
}

/**
 * 验证文件大小
 * @param file 文件对象
 * @param maxSize 最大大小（字节），默认50MB
 * @returns 是否在大小限制内
 */
export function isValidFileSize(file: File, maxSize: number = 50 * 1024 * 1024): boolean {
  return file.size <= maxSize;
}

/**
 * 生成唯一ID
 * @returns 唯一ID字符串
 */
export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}
