"""
Custom Error Classes

Defines all custom exception types used by the MCP Server.
"""

from typing import Optional


class MCPError(Exception):
    """MCP Tool Error Base Class"""

    def __init__(self, message: str, code: str = "MCP_ERROR", suggestion: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.suggestion:
            error_dict["suggestion"] = self.suggestion
        return error_dict


class DataNotFoundError(MCPError):
    """Data not found error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="DATA_NOT_FOUND",
            suggestion=suggestion or "Please check the date range or wait for crawling tasks to complete"
        )


class InvalidParameterError(MCPError):
    """Invalid parameter error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="INVALID_PARAMETER",
            suggestion=suggestion or "Please check if the parameter format is correct"
        )


class ConfigurationError(MCPError):
    """Configuration error"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            suggestion=suggestion or "Please check if the configuration file is correct"
        )


class PlatformNotSupportedError(MCPError):
    """Platform not supported error"""

    def __init__(self, platform: str):
        super().__init__(
            message=f"Platform '{platform}' is not supported",
            code="PLATFORM_NOT_SUPPORTED",
            suggestion="Supported platforms: zhihu, weibo, douyin, bilibili, baidu, toutiao, qq, 36kr, sspai, hellogithub, thepaper"
        )


class CrawlTaskError(MCPError):
    """爬取任务错误"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CRAWL_TASK_ERROR",
            suggestion=suggestion or "请稍后重试或查看日志"
        )


class FileParseError(MCPError):
    """文件解析错误"""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            message=f"解析文件 {file_path} 失败: {reason}",
            code="FILE_PARSE_ERROR",
            suggestion="请检查文件格式是否正确"
        )
