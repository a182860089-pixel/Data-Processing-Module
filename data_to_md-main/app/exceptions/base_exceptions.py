"""
基础异常类
"""


class BaseAppException(Exception):
    """应用基础异常"""
    
    def __init__(self, message: str, code: str = None, details: str = None):
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details
        super().__init__(self.message)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class ValidationError(BaseAppException):
    """验证错误"""
    pass


class ConfigurationError(BaseAppException):
    """配置错误"""
    pass


class FileOperationError(BaseAppException):
    """文件操作错误"""
    pass

