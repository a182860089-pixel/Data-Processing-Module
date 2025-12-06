"""
服务相关异常
"""
from app.exceptions.base_exceptions import BaseAppException


class ServiceException(BaseAppException):
    """服务基础异常"""
    pass


class APICallException(ServiceException):
    """API调用失败"""
    pass


class DeepSeekAPIException(APICallException):
    """DeepSeek API异常"""
    pass


class MinerUAPIException(APICallException):
    """MinerU API异常"""
    pass


class TaskNotFoundException(ServiceException):
    """任务不存在"""
    pass


class TaskProcessingException(ServiceException):
    """任务处理异常"""
    pass


class StorageException(ServiceException):
    """存储异常"""
    pass

