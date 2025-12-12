"""
微信公众号文章爬虫服务
使用 crawl4ai 爬取微信公众号文章内容并转换为 Markdown
"""
import logging
import re
import asyncio
from typing import Optional, Dict, Any
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

logger = logging.getLogger(__name__)


class WeChatCrawler:
    """微信公众号文章爬虫"""
    
    # 微信文章URL正则匹配
    WECHAT_URL_PATTERN = re.compile(
        r'^https?://mp\.weixin\.qq\.com/s[/?]'
    )
    
    def __init__(self):
        """初始化爬虫配置"""
        # 浏览器配置 - 模拟真实用户
        self.browser_config = BrowserConfig(
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
    
    def _is_wechat_url(self, url: str) -> bool:
        """验证是否为微信公众号文章URL"""
        return bool(self.WECHAT_URL_PATTERN.match(url))
    
    def _create_crawler_config(self, extract_images: bool = False) -> CrawlerRunConfig:
        """
        创建爬虫运行配置
        
        Args:
            extract_images: 是否提取图片链接
        """
        # 使用内容过滤器提取主要内容
        content_filter = PruningContentFilter(
            threshold=0.4,  # 内容相关性阈值
            threshold_type="fixed",
            min_word_threshold=20
        )
        
        # Markdown生成器配置
        md_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_links": not extract_images,  # 根据需求决定是否保留链接
                "ignore_images": not extract_images,
                "skip_internal_links": True,
                "escape_misc_chars": False
            }
        )
        
        return CrawlerRunConfig(
            markdown_generator=md_generator,
            wait_until="networkidle",  # 等待网络空闲，确保JS渲染完成
            page_timeout=30000,  # 30秒超时
            delay_before_return_html=2.0,  # 等待2秒让页面完全加载
            remove_overlay_elements=True,  # 移除弹窗覆盖层
            excluded_tags=["nav", "footer", "aside", "script", "style", "noscript"],
        )
    
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
            包含文章内容的字典:
            {
                "success": bool,
                "title": str,
                "content": str,  # Markdown格式内容
                "raw_markdown": str,  # 原始Markdown
                "url": str,
                "error": str (如果失败)
            }
        """
        # 验证URL
        if not self._is_wechat_url(url):
            logger.warning(f"非微信公众号URL: {url}")
            # 仍然尝试爬取，但记录警告
        
        logger.info(f"开始爬取文章: {url}")
        
        try:
            config = self._create_crawler_config(extract_images)
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(url, config=config),
                    timeout=timeout
                )
                
                if not result.success:
                    logger.error(f"爬取失败: {result.error_message}")
                    return {
                        "success": False,
                        "url": url,
                        "error": result.error_message or "爬取失败"
                    }
                
                # 提取文章标题
                title = self._extract_title(result)
                
                # 获取过滤后的Markdown内容
                fit_markdown = ""
                raw_markdown = ""
                
                if result.markdown:
                    if hasattr(result.markdown, 'fit_markdown'):
                        fit_markdown = result.markdown.fit_markdown or ""
                    if hasattr(result.markdown, 'raw_markdown'):
                        raw_markdown = result.markdown.raw_markdown or ""
                    # 兼容直接返回字符串的情况
                    if isinstance(result.markdown, str):
                        raw_markdown = result.markdown
                        fit_markdown = result.markdown
                
                # 清理内容
                content = self._clean_content(fit_markdown or raw_markdown)
                
                # 如果内容为空，尝试使用原始markdown
                if not content.strip() and raw_markdown:
                    content = self._clean_content(raw_markdown)
                
                logger.info(f"爬取成功: {title}, 内容长度: {len(content)}")
                
                return {
                    "success": True,
                    "title": title,
                    "content": content,
                    "raw_markdown": raw_markdown,
                    "url": url
                }
                
        except asyncio.TimeoutError:
            logger.error(f"爬取超时: {url}")
            return {
                "success": False,
                "url": url,
                "error": f"爬取超时（{timeout}秒）"
            }
        except Exception as e:
            logger.error(f"爬取异常: {url}, 错误: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
    
    def _extract_title(self, result) -> str:
        """从爬取结果中提取文章标题"""
        # 尝试从metadata获取
        if hasattr(result, 'metadata') and result.metadata:
            if isinstance(result.metadata, dict):
                title = result.metadata.get('title', '')
                if title:
                    return title.strip()
        
        # 尝试从HTML中提取
        if hasattr(result, 'html') and result.html:
            # 匹配微信文章标题
            title_match = re.search(
                r'<h1[^>]*class="[^"]*rich_media_title[^"]*"[^>]*>([^<]+)</h1>',
                result.html,
                re.IGNORECASE
            )
            if title_match:
                return title_match.group(1).strip()
            
            # 通用title标签匹配
            title_match = re.search(r'<title>([^<]+)</title>', result.html)
            if title_match:
                return title_match.group(1).strip()
        
        return "未知标题"
    
    def _clean_content(self, content: str) -> str:
        """清理Markdown内容"""
        if not content:
            return ""
        
        # 移除多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 移除微信特有的干扰内容
        patterns_to_remove = [
            r'阅读原文',
            r'点击.*?关注',
            r'长按.*?识别',
            r'扫码.*?关注',
            r'\[图片\]',
            r'!\[\]\([^)]*\)',  # 空图片标签
        ]
        
        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 清理首尾空白
        content = content.strip()
        
        return content
    
    async def crawl_multiple(
        self,
        urls: list[str],
        extract_images: bool = False,
        max_concurrent: int = 3
    ) -> list[Dict[str, Any]]:
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
        
        # 处理异常结果
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
