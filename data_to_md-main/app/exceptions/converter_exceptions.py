"""
转换器相关异常
"""
from app.exceptions.base_exceptions import BaseAppException


class ConverterException(BaseAppException):
    """转换器基础异常"""
    pass


class UnsupportedFileTypeException(ConverterException):
    """不支持的文件类型"""
    pass


class ConversionFailedException(ConverterException):
    """转换失败"""
    pass


class FileValidationException(ConverterException):
    """文件验证失败"""
    pass


class FileTooLargeException(ConverterException):
    """文件过大"""
    pass


class InvalidFileException(ConverterException):
    """无效文件"""
    pass

