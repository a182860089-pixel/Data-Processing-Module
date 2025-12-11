import { ref } from "vue";

// 后端 API 基础地址
const API_BASE_URL =
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  import.meta.env.VITE_PDF_API_BASE_URL ||
  "http://localhost:8000";

interface ConvertResponse {
  success: boolean;
  task_id: string;
  message: string;
  filename: string;
  file_type: string;
  download_url: string;
  metadata: {
    image_count: number;
    pages_processed: number;
    processing_time: number;
    file_size: number;
    output_type: string;
  };
}

export function useMultiImageToPdf() {
  const converting = ref(false);
  const progress = ref(0);
  const error = ref<string | null>(null);

  /**
   * 将多张图片转换为 PDF
   */
  const convertImagesToPdf = async (
    files: File[],
    options: {
      page_size?: string;
      fit_mode?: string;
    } = {}
  ): Promise<{
    taskId: string;
    filename: string;
    downloadUrl: string;
    metadata: Record<string, any>;
  }> => {
    converting.value = true;
    progress.value = 5;
    error.value = null;

    try {
      if (!files || files.length === 0) {
        throw new Error("请选择至少一张图片");
      }

      const formData = new FormData();

      // 添加所有图片文件
      files.forEach((file) => {
        formData.append("files", file);
      });

      // 添加转换选项
      const convertOptions = {
        page_size: options.page_size || "A4",
        fit_mode: options.fit_mode || "fit",
      };
      formData.append("options", JSON.stringify(convertOptions));

      progress.value = 20;

      // 调用后端多文件转PDF接口
      const response = await fetch(`${API_BASE_URL}/api/v1/convert/images`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let detail = "";
        try {
          const data = await response.json();
          detail =
            (data?.detail &&
              (data.detail.message ||
                data.detail.details ||
                data.detail)) ||
            JSON.stringify(data);
        } catch {
          detail = response.statusText;
        }
        throw new Error(
          `多图片转PDF失败 (${response.status}): ${detail}`
        );
      }

      const data = (await response.json()) as ConvertResponse;
      if (!data.success) {
        throw new Error(data.message || "多图片转PDF失败");
      }

      progress.value = 100;
      converting.value = false;

      return {
        taskId: data.task_id,
        filename: data.filename,
        downloadUrl: data.download_url.startsWith("http")
          ? data.download_url
          : `${API_BASE_URL}${data.download_url}`,
        metadata: data.metadata,
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : "多图片转PDF失败";
      error.value = msg;
      converting.value = false;
      progress.value = 0;
      throw new Error(msg);
    }
  };

  return {
    converting,
    progress,
    error,
    convertImagesToPdf,
  };
}
