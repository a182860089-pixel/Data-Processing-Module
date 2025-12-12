"""
调试页面：提供一个简单的前端页面用于上传文件与选择 OCR 引擎
访问路径：GET /api/v1/debug
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


def _html_page() -> str:
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>调试面板 - PDF 转换</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif; margin: 24px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    label { font-weight: 600; }
    input[type="file"]{ width: 100%; }
    select, input[type="checkbox"], input[type="number"], input[type="text"] { padding: 6px; }
    button { padding: 8px 16px; cursor: pointer; }
    textarea { width: 100%; height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
    .hint { color: #666; font-size: 12px; }
    .row > * { margin: 4px 0; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; background: #eef; color: #335; margin-left: 6px; font-size: 12px; }
  </style>
</head>
<body>
  <h2>PDF 转换调试面板 <span class="badge">/api/v1/convert</span></h2>
  <div class="card">
    <div class="row">
      <div>
        <label>选择文件：</label><br/>
        <input id="file" type="file" accept="application/pdf" />
      </div>
      <div>
        <label>OCR 引擎：</label><br/>
        <select id="engine">
          <option value="deepseek">deepseek</option>
          <option value="mineru">mineru</option>
          <option value="auto">auto</option>
        </select>
      </div>
      <div>
        <label><input type="checkbox" id="noPagMeta" /> 无分页且不含元数据</label>
        <div class="hint">等价于 no_pagination_and_metadata=true</div>
      </div>
      <div>
        <label>DPI：</label><br/>
        <input id="dpi" type="number" value="144" min="72" max="300" />
      </div>
    </div>
    <div class="row">
      <button id="btn">开始转换</button>
      <div id="status" class="hint"></div>
    </div>
  </div>

  <div class="card">
    <label>响应 JSON：</label>
    <textarea id="resp" readonly></textarea>
  </div>

  <div class="card">
    <label>Markdown 预览（只读）：</label>
    <textarea id="md" readonly></textarea>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);

    function buildOptions() {
      const engine = $("engine").value;
      const noPagMeta = $("noPagMeta").checked;
      const dpi = parseInt($("dpi").value || '144', 10);
      const options = {
        dpi,
        ocr_engine: engine,
        include_metadata: !noPagMeta,
        show_page_number: !noPagMeta,
        no_pagination_and_metadata: !!noPagMeta,
        async: false
      };
      // 对 mineru 模式，默认建议不分页不元数据（整文输出更合适）
      if (engine === 'mineru') {
        options.no_pagination_and_metadata = true;
        options.include_metadata = false;
        options.show_page_number = false;
      }
      return options;
    }

    async function doUpload() {
      const f = $("file").files[0];
      if (!f) { alert("请先选择文件"); return; }
      const form = new FormData();
      form.append('file', f);
      form.append('options', JSON.stringify(buildOptions()));

      $("status").textContent = '上传中...';
      try {
        const res = await fetch('/api/v1/convert', {
          method: 'POST',
          body: form
        });
        const data = await res.json();
        $("resp").value = JSON.stringify(data, null, 2);
        if (data && data.markdown_content) {
          $("md").value = data.markdown_content;
        } else {
          $("md").value = '';
        }
        $("status").textContent = res.ok ? '完成' : '失败';
      } catch (e) {
        $("resp").value = String(e);
        $("status").textContent = '异常';
      }
    }

    $("btn").addEventListener('click', doUpload);
  </script>
</body>
</html>
"""


@router.get("/debug", response_class=HTMLResponse)
async def debug_ui():
    """返回内置的调试页面"""
    return HTMLResponse(content=_html_page(), status_code=200)
