"""
微信公众号文章爬虫服务
使用 crawl4ai 爬取微信公众号文章内容并转换为 Markdown

重要：Windows 上 uvicorn 的事件循环与 Playwright 的 subprocess 不兼容，
因此将 crawl4ai 操作放到独立线程中执行。
"""
import logging
import re
import asyncio
import concurrent.futures
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# 创建一个专用的线程池执行器（用于运行 Playwright）
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="crawler")


def _run_crawl_in_thread(url: str, extract_images: bool, timeout: int) -> Dict[str, Any]:
    """
    在独立线程中运行爬虫（同步函数）

    关键点：Windows 上只有 ProactorEventLoop 支持 asyncio subprocess。
    uvicorn/依赖可能将全局策略切到 SelectorEventLoopPolicy，从而导致
    Playwright 在 asyncio.create_subprocess_exec 处抛 NotImplementedError。

    因此这里在“线程内部”显式创建 Proactor 事件循环。
    """
    import asyncio
    import sys

    async def _do_crawl():
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
        from crawl4ai.content_filter_strategy import PruningContentFilter
        
        # 浏览器配置
        browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            viewport_width=1280,
            viewport_height=800,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            verbose=False,
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ]
        )
        
        # 内容过滤器
        content_filter = PruningContentFilter(
            threshold=0.4,
            threshold_type="fixed",
            min_word_threshold=20
        )
        
        # Markdown生成器
        md_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_links": not extract_images,
                "ignore_images": not extract_images,
                "skip_internal_links": True,
                "escape_misc_chars": False
            }
        )
        
        # 爬虫配置
        crawler_config = CrawlerRunConfig(
            markdown_generator=md_generator,
            wait_until="networkidle",
            page_timeout=30000,
            delay_before_return_html=2.0,
            remove_overlay_elements=True,
            excluded_tags=["nav", "footer", "aside", "script", "style", "noscript"],
        )
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(url, config=crawler_config),
                    timeout=timeout
                )
                
                if not result.success:
                    return {
                        "success": False,
                        "url": url,
                        "error": result.error_message or "爬取失败"
                    }
                
                # 提取标题
                title = _extract_title_from_result(result)
                
                # 提取Markdown内容
                fit_markdown = ""
                raw_markdown = ""
                
                if result.markdown:
                    if hasattr(result.markdown, 'fit_markdown'):
                        fit_markdown = result.markdown.fit_markdown or ""
                    if hasattr(result.markdown, 'raw_markdown'):
                        raw_markdown = result.markdown.raw_markdown or ""
                    if isinstance(result.markdown, str):
                        raw_markdown = result.markdown
                        fit_markdown = result.markdown
                
                content = _clean_markdown_content(fit_markdown or raw_markdown)
                if not content.strip() and raw_markdown:
                    content = _clean_markdown_content(raw_markdown)
                
                return {
                    "success": True,
                    "title": title,
                    "content": content,
                    "raw_markdown": raw_markdown,
                    "url": url
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "url": url,
                "error": f"爬取超时（{timeout}秒）",
            }
        except Exception as e:
            msg = str(e) or repr(e)
            return {
                "success": False,
                "url": url,
                "error": msg,
            }

    # 在当前线程中创建“支持 subprocess”的事件循环并运行
    if sys.platform == "win32":
        try:
            import asyncio.windows_events as windows_events

            loop = windows_events.ProactorEventLoop()
        except Exception:
            # 兜底：显式设置策略后再创建
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
    else:
        loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_do_crawl())
    finally:
        # 尽量取消残留任务，避免 "Task exception was never retrieved"
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()


def _extract_title_from_result(result) -> str:
    """从爬取结果中提取文章标题"""
    if hasattr(result, 'metadata') and result.metadata:
        if isinstance(result.metadata, dict):
            title = result.metadata.get('title', '')
            if title:
                return title.strip()
    
    if hasattr(result, 'html') and result.html:
        # 微信文章标题
        title_match = re.search(
            r'<h1[^>]*class="[^"]*rich_media_title[^"]*"[^>]*>([^<]+)</h1>',
            result.html,
            re.IGNORECASE
        )
        if title_match:
            return title_match.group(1).strip()
        
        # 通用title
        title_match = re.search(r'<title>([^<]+)</title>', result.html)
        if title_match:
            return title_match.group(1).strip()
    
    return "未知标题"


def _clean_markdown_content(content: str) -> str:
    """清理Markdown内容"""
    if not content:
        return ""
    
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    patterns_to_remove = [
        r'阅读原文',
        r'点击.*?关注',
        r'长按.*?识别',
        r'扫码.*?关注',
        r'\[图片\]',
        r'!\[\]\([^)]*\)',
    ]
    
    for pattern in patterns_to_remove:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    return content.strip()


class WeChatCrawler:
    """微信公众号文章爬虫"""
    
    WECHAT_URL_PATTERN = re.compile(r'^https?://mp\.weixin\.qq\.com/s[/?]')
    
    def __init__(self):
        """初始化爬虫"""
        pass
    
    def _is_wechat_url(self, url: str) -> bool:
        """验证是否为微信公众号文章URL"""
        return bool(self.WECHAT_URL_PATTERN.match(url))
    
    async def crawl_article(
        self,
        url: str,
        extract_images: bool = False,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        爬取微信公众号文章
        
        Args:
            url: 微信公众号文章URL
            extract_images: 是否提取图片
            timeout: 超时时间（秒）
            
        Returns:
            包含文章内容的字典
        """
        if not self._is_wechat_url(url):
            logger.warning(f"非微信公众号URL: {url}")
        
        logger.info(f"开始爬取文章: {url}")
        
        try:
            # 在线程池中执行爬虫操作，避免 asyncio 事件循环冲突
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                _executor,
                _run_crawl_in_thread,
                url,
                extract_images,
                timeout
            )
            
            if result.get("success"):
                logger.info(f"爬取成功: {result.get('title')}, 内容长度: {len(result.get('content', ''))}")
            else:
                logger.error(f"爬取失败: {url}, 错误: {result.get('error')}")
            
            return result
            
        except Exception as e:
            msg = str(e) or repr(e)
            logger.error(f"爬取异常: {url}, 错误: {msg}")
            return {
                "success": False,
                "url": url,
                "error": msg,
            }
    
    async def crawl_multiple(
        self,
        urls: List[str],
        extract_images: bool = False,
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        批量爬取多篇文章
        
        Args:
            urls: 文章URL列表
            extract_images: 是否提取图片
            max_concurrent: 最大并发数
            
        Returns:
            爬取结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url: str):
            async with semaphore:
                return await self.crawl_article(url, extract_images)
        
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "url": urls[i],
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
