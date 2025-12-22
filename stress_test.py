"""
压力测试脚本 - 多并发多线程文件上传转换测试

功能：
1. 多线程并发上传文件
2. 支持同步和异步转换接口
3. 统计成功率、响应时间、吞吐量
4. 生成测试报告

使用方法：
    python stress_test.py --url http://localhost:8000 --files ./test_files --concurrency 10 --requests 100
"""

import argparse
import asyncio
import aiohttp
import os
import time
import statistics
import json
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import threading
import requests
from collections import defaultdict


@dataclass
class TestResult:
    """单个测试结果"""
    success: bool
    status_code: int
    response_time: float  # 秒
    file_name: str
    file_size: int
    error_message: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: int = 0


@dataclass
class TestReport:
    """测试报告"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    results: List[TestResult] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)
    
    @property
    def min_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return min(self.response_times)
    
    @property
    def max_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return max(self.response_times)
    
    @property
    def p50_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)
    
    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.max_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]
    
    @property
    def p99_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.max_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]
    
    @property
    def throughput(self) -> float:
        """每秒处理请求数"""
        if self.total_time == 0:
            return 0.0
        return self.total_requests / self.total_time


class StressTest:
    """压力测试类"""
    
    SUPPORTED_EXTENSIONS = {
        '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.tiff', '.bmp',
        '.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv'
    }
    
    def __init__(
        self,
        base_url: str,
        test_files_dir: str,
        concurrency: int = 10,
        total_requests: int = 100,
        use_async_api: bool = False,
        timeout: int = 300
    ):
        self.base_url = base_url.rstrip('/')
        self.test_files_dir = Path(test_files_dir)
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.use_async_api = use_async_api
        self.timeout = timeout
        self.report = TestReport()
        self.lock = threading.Lock()
        self.test_files: List[Path] = []
        
    def discover_test_files(self) -> List[Path]:
        """发现测试文件"""
        files = []
        if self.test_files_dir.is_file():
            files.append(self.test_files_dir)
        elif self.test_files_dir.is_dir():
            for ext in self.SUPPORTED_EXTENSIONS:
                files.extend(self.test_files_dir.glob(f'*{ext}'))
                files.extend(self.test_files_dir.glob(f'*{ext.upper()}'))
        
        if not files:
            raise ValueError(f"未找到测试文件: {self.test_files_dir}")
        
        print(f"发现 {len(files)} 个测试文件:")
        for f in files[:10]:
            print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        if len(files) > 10:
            print(f"  ... 还有 {len(files) - 10} 个文件")
        
        return files
    
    def upload_file_sync(self, file_path: Path, thread_id: int) -> TestResult:
        """同步上传文件"""
        start_time = time.time()
        file_size = file_path.stat().st_size
        
        endpoint = "/api/v1/convert/async" if self.use_async_api else "/api/v1/convert"
        url = f"{self.base_url}{endpoint}"
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                response = requests.post(
                    url,
                    files=files,
                    timeout=self.timeout
                )
            
            response_time = time.time() - start_time
            success = response.status_code == 200
            
            task_id = None
            error_message = None
            
            if success:
                try:
                    data = response.json()
                    task_id = data.get('task_id')
                except:
                    pass
            else:
                try:
                    error_message = response.json().get('detail', response.text[:200])
                except:
                    error_message = response.text[:200]
            
            return TestResult(
                success=success,
                status_code=response.status_code,
                response_time=response_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message=error_message,
                task_id=task_id,
                thread_id=thread_id
            )
            
        except requests.exceptions.Timeout:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message="请求超时",
                thread_id=thread_id
            )
        except requests.exceptions.ConnectionError as e:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message=f"连接错误: {str(e)[:100]}",
                thread_id=thread_id
            )
        except Exception as e:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message=f"异常: {str(e)[:100]}",
                thread_id=thread_id
            )
    
    def worker(self, task_id: int, file_path: Path) -> TestResult:
        """工作线程"""
        thread_id = threading.current_thread().ident
        result = self.upload_file_sync(file_path, thread_id)
        
        with self.lock:
            self.report.results.append(result)
            self.report.total_requests += 1
            self.report.response_times.append(result.response_time)
            
            if result.success:
                self.report.successful_requests += 1
            else:
                self.report.failed_requests += 1
                error_key = result.error_message or f"HTTP {result.status_code}"
                self.report.errors[error_key] += 1
            
            # 打印进度
            progress = (self.report.total_requests / self.total_requests) * 100
            status = "✓" if result.success else "✗"
            print(f"[{progress:5.1f}%] {status} {result.file_name} - {result.response_time:.2f}s")
        
        return result
    
    def run_threaded_test(self):
        """运行多线程测试"""
        print(f"\n{'='*60}")
        print(f"开始压力测试")
        print(f"{'='*60}")
        print(f"目标地址: {self.base_url}")
        print(f"并发数: {self.concurrency}")
        print(f"总请求数: {self.total_requests}")
        print(f"API模式: {'异步' if self.use_async_api else '同步'}")
        print(f"超时时间: {self.timeout}s")
        print(f"{'='*60}\n")
        
        # 发现测试文件
        self.test_files = self.discover_test_files()
        
        # 准备任务列表
        tasks = []
        for i in range(self.total_requests):
            file_path = random.choice(self.test_files)
            tasks.append((i, file_path))
        
        # 开始测试
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = [
                executor.submit(self.worker, task_id, file_path)
                for task_id, file_path in tasks
            ]
            
            # 等待所有任务完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"任务异常: {e}")
        
        self.report.total_time = time.time() - start_time
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report = f"""
{'='*60}
                    压力测试报告
{'='*60}
测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
目标地址: {self.base_url}
并发数: {self.concurrency}
API模式: {'异步' if self.use_async_api else '同步'}

{'─'*60}
                    汇总统计
{'─'*60}
总请求数:     {self.report.total_requests}
成功请求数:   {self.report.successful_requests}
失败请求数:   {self.report.failed_requests}
成功率:       {self.report.success_rate:.2f}%
总耗时:       {self.report.total_time:.2f}s
吞吐量:       {self.report.throughput:.2f} req/s

{'─'*60}
                    响应时间统计
{'─'*60}
平均响应时间:  {self.report.avg_response_time:.3f}s
最小响应时间:  {self.report.min_response_time:.3f}s
最大响应时间:  {self.report.max_response_time:.3f}s
P50响应时间:   {self.report.p50_response_time:.3f}s
P95响应时间:   {self.report.p95_response_time:.3f}s
P99响应时间:   {self.report.p99_response_time:.3f}s
"""
        
        if self.report.errors:
            report += f"""
{'─'*60}
                    错误统计
{'─'*60}
"""
            for error, count in sorted(self.report.errors.items(), key=lambda x: -x[1]):
                report += f"{error[:50]:50s} : {count}\n"
        
        report += f"""
{'='*60}
"""
        return report
    
    def save_report(self, output_file: str = "stress_test_report.json"):
        """保存详细报告到JSON文件"""
        report_data = {
            "test_config": {
                "base_url": self.base_url,
                "concurrency": self.concurrency,
                "total_requests": self.total_requests,
                "use_async_api": self.use_async_api,
                "timeout": self.timeout,
                "test_time": datetime.now().isoformat()
            },
            "summary": {
                "total_requests": self.report.total_requests,
                "successful_requests": self.report.successful_requests,
                "failed_requests": self.report.failed_requests,
                "success_rate": self.report.success_rate,
                "total_time": self.report.total_time,
                "throughput": self.report.throughput
            },
            "response_times": {
                "avg": self.report.avg_response_time,
                "min": self.report.min_response_time,
                "max": self.report.max_response_time,
                "p50": self.report.p50_response_time,
                "p95": self.report.p95_response_time,
                "p99": self.report.p99_response_time
            },
            "errors": dict(self.report.errors),
            "results": [
                {
                    "success": r.success,
                    "status_code": r.status_code,
                    "response_time": r.response_time,
                    "file_name": r.file_name,
                    "file_size": r.file_size,
                    "error_message": r.error_message,
                    "task_id": r.task_id
                }
                for r in self.report.results
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n详细报告已保存到: {output_file}")


class AsyncStressTest:
    """异步压力测试类 (使用 aiohttp)"""
    
    SUPPORTED_EXTENSIONS = StressTest.SUPPORTED_EXTENSIONS
    
    def __init__(
        self,
        base_url: str,
        test_files_dir: str,
        concurrency: int = 10,
        total_requests: int = 100,
        use_async_api: bool = False,
        timeout: int = 300
    ):
        self.base_url = base_url.rstrip('/')
        self.test_files_dir = Path(test_files_dir)
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.use_async_api = use_async_api
        self.timeout = timeout
        self.report = TestReport()
        self.test_files: List[Path] = []
        self.semaphore: asyncio.Semaphore = None
        self.progress_lock = asyncio.Lock()
        
    def discover_test_files(self) -> List[Path]:
        """发现测试文件"""
        files = []
        if self.test_files_dir.is_file():
            files.append(self.test_files_dir)
        elif self.test_files_dir.is_dir():
            for ext in self.SUPPORTED_EXTENSIONS:
                files.extend(self.test_files_dir.glob(f'*{ext}'))
                files.extend(self.test_files_dir.glob(f'*{ext.upper()}'))
        
        if not files:
            raise ValueError(f"未找到测试文件: {self.test_files_dir}")
        
        print(f"发现 {len(files)} 个测试文件:")
        for f in files[:10]:
            print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        if len(files) > 10:
            print(f"  ... 还有 {len(files) - 10} 个文件")
        
        return files
    
    async def upload_file_async(
        self,
        session: aiohttp.ClientSession,
        file_path: Path,
        task_id: int
    ) -> TestResult:
        """异步上传文件"""
        start_time = time.time()
        file_size = file_path.stat().st_size
        
        endpoint = "/api/v1/convert/async" if self.use_async_api else "/api/v1/convert"
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.semaphore:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        'file',
                        f,
                        filename=file_path.name,
                        content_type='application/octet-stream'
                    )
                    
                    async with session.post(
                        url,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        response_time = time.time() - start_time
                        success = response.status == 200
                        
                        result_task_id = None
                        error_message = None
                        
                        try:
                            resp_data = await response.json()
                            if success:
                                result_task_id = resp_data.get('task_id')
                            else:
                                error_message = resp_data.get('detail', str(resp_data)[:200])
                        except:
                            if not success:
                                error_message = await response.text()
                                error_message = error_message[:200]
                        
                        return TestResult(
                            success=success,
                            status_code=response.status,
                            response_time=response_time,
                            file_name=file_path.name,
                            file_size=file_size,
                            error_message=error_message,
                            task_id=result_task_id,
                            thread_id=task_id
                        )
                        
        except asyncio.TimeoutError:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message="请求超时",
                thread_id=task_id
            )
        except aiohttp.ClientError as e:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message=f"连接错误: {str(e)[:100]}",
                thread_id=task_id
            )
        except Exception as e:
            return TestResult(
                success=False,
                status_code=0,
                response_time=time.time() - start_time,
                file_name=file_path.name,
                file_size=file_size,
                error_message=f"异常: {str(e)[:100]}",
                thread_id=task_id
            )
    
    async def worker(
        self,
        session: aiohttp.ClientSession,
        task_id: int,
        file_path: Path
    ) -> TestResult:
        """异步工作协程"""
        result = await self.upload_file_async(session, file_path, task_id)
        
        async with self.progress_lock:
            self.report.results.append(result)
            self.report.total_requests += 1
            self.report.response_times.append(result.response_time)
            
            if result.success:
                self.report.successful_requests += 1
            else:
                self.report.failed_requests += 1
                error_key = result.error_message or f"HTTP {result.status_code}"
                self.report.errors[error_key] += 1
            
            # 打印进度
            progress = (self.report.total_requests / self.total_requests) * 100
            status = "✓" if result.success else "✗"
            print(f"[{progress:5.1f}%] {status} {result.file_name} - {result.response_time:.2f}s")
        
        return result
    
    async def run_async_test(self):
        """运行异步测试"""
        print(f"\n{'='*60}")
        print(f"开始异步压力测试")
        print(f"{'='*60}")
        print(f"目标地址: {self.base_url}")
        print(f"并发数: {self.concurrency}")
        print(f"总请求数: {self.total_requests}")
        print(f"API模式: {'异步' if self.use_async_api else '同步'}")
        print(f"超时时间: {self.timeout}s")
        print(f"{'='*60}\n")
        
        # 发现测试文件
        self.test_files = self.discover_test_files()
        
        # 初始化信号量
        self.semaphore = asyncio.Semaphore(self.concurrency)
        
        # 准备任务列表
        tasks_data = []
        for i in range(self.total_requests):
            file_path = random.choice(self.test_files)
            tasks_data.append((i, file_path))
        
        # 开始测试
        start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=self.concurrency * 2)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                self.worker(session, task_id, file_path)
                for task_id, file_path in tasks_data
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.report.total_time = time.time() - start_time
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report = f"""
{'='*60}
                    异步压力测试报告
{'='*60}
测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
目标地址: {self.base_url}
并发数: {self.concurrency}
API模式: {'异步' if self.use_async_api else '同步'}

{'─'*60}
                    汇总统计
{'─'*60}
总请求数:     {self.report.total_requests}
成功请求数:   {self.report.successful_requests}
失败请求数:   {self.report.failed_requests}
成功率:       {self.report.success_rate:.2f}%
总耗时:       {self.report.total_time:.2f}s
吞吐量:       {self.report.throughput:.2f} req/s

{'─'*60}
                    响应时间统计
{'─'*60}
平均响应时间:  {self.report.avg_response_time:.3f}s
最小响应时间:  {self.report.min_response_time:.3f}s
最大响应时间:  {self.report.max_response_time:.3f}s
P50响应时间:   {self.report.p50_response_time:.3f}s
P95响应时间:   {self.report.p95_response_time:.3f}s
P99响应时间:   {self.report.p99_response_time:.3f}s
"""
        
        if self.report.errors:
            report += f"""
{'─'*60}
                    错误统计
{'─'*60}
"""
            for error, count in sorted(self.report.errors.items(), key=lambda x: -x[1]):
                report += f"{error[:50]:50s} : {count}\n"
        
        report += f"""
{'='*60}
"""
        return report
    
    def save_report(self, output_file: str = "stress_test_report.json"):
        """保存详细报告到JSON文件"""
        report_data = {
            "test_config": {
                "base_url": self.base_url,
                "concurrency": self.concurrency,
                "total_requests": self.total_requests,
                "use_async_api": self.use_async_api,
                "timeout": self.timeout,
                "test_time": datetime.now().isoformat(),
                "mode": "async"
            },
            "summary": {
                "total_requests": self.report.total_requests,
                "successful_requests": self.report.successful_requests,
                "failed_requests": self.report.failed_requests,
                "success_rate": self.report.success_rate,
                "total_time": self.report.total_time,
                "throughput": self.report.throughput
            },
            "response_times": {
                "avg": self.report.avg_response_time,
                "min": self.report.min_response_time,
                "max": self.report.max_response_time,
                "p50": self.report.p50_response_time,
                "p95": self.report.p95_response_time,
                "p99": self.report.p99_response_time
            },
            "errors": dict(self.report.errors),
            "results": [
                {
                    "success": r.success,
                    "status_code": r.status_code,
                    "response_time": r.response_time,
                    "file_name": r.file_name,
                    "file_size": r.file_size,
                    "error_message": r.error_message,
                    "task_id": r.task_id
                }
                for r in self.report.results
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n详细报告已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='文件转换服务压力测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础测试（10并发，100请求）
  python stress_test.py --url http://localhost:8000 --files ./test_files

  # 高并发测试
  python stress_test.py --url http://localhost:8000 --files ./test_files -c 50 -n 500

  # 使用异步API接口
  python stress_test.py --url http://localhost:8000 --files ./test_files --async-api

  # 使用异步HTTP客户端（更高性能）
  python stress_test.py --url http://localhost:8000 --files ./test_files --async-mode

  # 测试单个文件
  python stress_test.py --url http://localhost:8000 --files ./test.pdf -c 20 -n 100
        """
    )
    
    parser.add_argument(
        '--url', '-u',
        required=True,
        help='目标服务URL (例如: http://localhost:8000)'
    )
    parser.add_argument(
        '--files', '-f',
        required=True,
        help='测试文件目录或单个文件路径'
    )
    parser.add_argument(
        '--concurrency', '-c',
        type=int,
        default=10,
        help='并发数 (默认: 10)'
    )
    parser.add_argument(
        '--requests', '-n',
        type=int,
        default=100,
        help='总请求数 (默认: 100)'
    )
    parser.add_argument(
        '--async-api',
        action='store_true',
        help='使用异步转换API (/api/v1/convert/async)'
    )
    parser.add_argument(
        '--async-mode',
        action='store_true',
        help='使用异步HTTP客户端 (aiohttp)'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=300,
        help='单个请求超时时间(秒) (默认: 300)'
    )
    parser.add_argument(
        '--output', '-o',
        default='stress_test_report.json',
        help='输出报告文件名 (默认: stress_test_report.json)'
    )
    
    args = parser.parse_args()
    
    # 检查服务是否可用
    try:
        response = requests.get(f"{args.url}/api/v1/health", timeout=10)
        if response.status_code != 200:
            print(f"警告: 服务健康检查失败 (HTTP {response.status_code})")
    except Exception as e:
        print(f"警告: 无法连接到服务 {args.url}: {e}")
        print("继续执行测试...\n")
    
    # 选择测试模式
    if args.async_mode:
        tester = AsyncStressTest(
            base_url=args.url,
            test_files_dir=args.files,
            concurrency=args.concurrency,
            total_requests=args.requests,
            use_async_api=args.async_api,
            timeout=args.timeout
        )
        asyncio.run(tester.run_async_test())
    else:
        tester = StressTest(
            base_url=args.url,
            test_files_dir=args.files,
            concurrency=args.concurrency,
            total_requests=args.requests,
            use_async_api=args.async_api,
            timeout=args.timeout
        )
        tester.run_threaded_test()
    
    # 生成并打印报告
    print(tester.generate_report())
    
    # 保存详细报告
    tester.save_report(args.output)


if __name__ == '__main__':
    main()
