"""
网页爬虫接口
支持微信公众号文章爬取并转换为 Markdown

注意：该模块依赖可选第三方库 `crawl4ai`。
如果环境未安装对应依赖，服务仍可启动，但访问爬虫相关接口会返回 503。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_wechat_crawler():
    """延迟导入 WeChatCrawler，避免在未安装 crawl4ai 时导致应用启动失败。"""
    try:
        from app.services.crawler.wechat_crawler import WeChatCrawler  # noqa: WPS433

        return WeChatCrawler()
    except ModuleNotFoundError as e:
        # 典型：No module named 'crawl4ai'
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CRAWLER_DEPENDENCY_MISSING",
                "message": "爬虫依赖未安装（缺少 crawl4ai），当前环境无法使用爬虫接口",
                "details": str(e),
                "hint": "请在后端环境中执行：pip install -r requirements.txt（或单独安装 crawl4ai）",
            },
        ) from e


# ==================== 请求模型 ====================

class CrawlRequest(BaseModel):
    """单篇文章爬取请求"""
    url: str = Field(..., description="微信公众号文章URL")
    extract_images: bool = Field(default=False, description="是否提取图片链接")
    timeout: int = Field(default=60, ge=10, le=300, description="超时时间（秒）")


class BatchCrawlRequest(BaseModel):
    """批量爬取请求"""
    urls: List[str] = Field(..., min_length=1, max_length=20, description="文章URL列表（最多20个）")
    extract_images: bool = Field(default=False, description="是否提取图片链接")
    max_concurrent: int = Field(default=3, ge=1, le=5, description="最大并发数")


# ==================== 响应模型 ====================

class CrawlResult(BaseModel):
    """爬取结果"""
    success: bool = Field(..., description="是否成功")
    title: Optional[str] = Field(None, description="文章标题")
    content: Optional[str] = Field(None, description="Markdown内容")
    url: str = Field(..., description="原始URL")
    error: Optional[str] = Field(None, description="错误信息")


class CrawlResponse(BaseModel):
    """单篇爬取响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    data: Optional[CrawlResult] = Field(None, description="爬取结果")


class BatchCrawlResponse(BaseModel):
    """批量爬取响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    total: int = Field(..., description="总数")
    success_count: int = Field(..., description="成功数")
    failed_count: int = Field(..., description="失败数")
    results: List[CrawlResult] = Field(..., description="爬取结果列表")


# ==================== API 端点 ====================

@router.post(
    "/crawl/wechat",
    response_model=CrawlResponse,
    summary="爬取微信公众号文章",
    description="爬取单篇微信公众号文章，将正文内容转换为 Markdown 格式"
)
async def crawl_wechat_article(request: CrawlRequest):
    """
    爬取微信公众号文章
    
    - **url**: 微信公众号文章链接 (https://mp.weixin.qq.com/s/...)
    - **extract_images**: 是否在Markdown中保留图片链接
    - **timeout**: 爬取超时时间
    
    返回文章标题和 Markdown 格式的正文内容
    """
    try:
        crawler = _get_wechat_crawler()
        result = await crawler.crawl_article(
            url=request.url,
            extract_images=request.extract_images,
            timeout=request.timeout,
        )
        
        if result["success"]:
            return CrawlResponse(
                success=True,
                message="文章爬取成功",
                data=CrawlResult(
                    success=True,
                    title=result.get("title"),
                    content=result.get("content"),
                    url=result["url"]
                )
            )
        else:
            return CrawlResponse(
                success=False,
                message=f"文章爬取失败: {result.get('error', '未知错误')}",
                data=CrawlResult(
                    success=False,
                    url=result["url"],
                    error=result.get("error")
                )
            )
            
    except Exception as e:
        logger.error(f"爬取异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "CRAWL_ERROR",
                "message": "爬取过程发生错误",
                "details": str(e)
            }
        )


@router.post(
    "/crawl/wechat/batch",
    response_model=BatchCrawlResponse,
    summary="批量爬取微信公众号文章",
    description="批量爬取多篇微信公众号文章（最多20篇）"
)
async def batch_crawl_wechat_articles(request: BatchCrawlRequest):
    """
    批量爬取微信公众号文章
    
    - **urls**: 文章URL列表（最多20个）
    - **extract_images**: 是否保留图片链接
    - **max_concurrent**: 最大并发数（1-5）
    
    返回每篇文章的爬取结果
    """
    try:
        crawler = _get_wechat_crawler()
        results = await crawler.crawl_multiple(
            urls=request.urls,
            extract_images=request.extract_images,
            max_concurrent=request.max_concurrent,
        )
        
        # 统计结果
        success_count = sum(1 for r in results if r.get("success"))
        failed_count = len(results) - success_count
        
        # 转换结果格式
        crawl_results = [
            CrawlResult(
                success=r.get("success", False),
                title=r.get("title"),
                content=r.get("content"),
                url=r.get("url", ""),
                error=r.get("error")
            )
            for r in results
        ]
        
        return BatchCrawlResponse(
            success=success_count > 0,
            message=f"批量爬取完成: {success_count}成功, {failed_count}失败",
            total=len(results),
            success_count=success_count,
            failed_count=failed_count,
            results=crawl_results
        )
        
    except Exception as e:
        logger.error(f"批量爬取异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "BATCH_CRAWL_ERROR",
                "message": "批量爬取过程发生错误",
                "details": str(e)
            }
        )


@router.get(
    "/crawl/test",
    summary="测试爬虫服务",
    description="测试爬虫服务是否正常运行"
)
async def test_crawler():
    """测试爬虫服务状态"""
    return {
        "status": "ok",
        "message": "爬虫服务运行正常",
        "supported_sites": ["mp.weixin.qq.com"]
    }
