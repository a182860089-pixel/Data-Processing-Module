/**
 * 下载文件
 * @param blob Blob对象
 * @param fileName 文件名
 */
export function downloadFile(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 从文件名生成WebP文件名
 * @param originalFileName 原始文件名
 * @returns WebP文件名
 */
export function generateWebPFileName(originalFileName: string): string {
  const nameWithoutExt = originalFileName.replace(/\.[^/.]+$/, '')
  return `${nameWithoutExt}.webp`
}

/**
 * 读取文件为ArrayBuffer
 * @param file 文件对象
 * @returns Promise<ArrayBuffer>
 */
export function readFileAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = reject
    reader.readAsArrayBuffer(file)
  })
}

