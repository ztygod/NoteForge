"""认证生命周期中可供业务层分类处理的异常。"""

from noteforge.exceptions.base import NoteForgeError


class AuthError(NoteForgeError):
    """认证错误基类。"""


class AuthRequiredError(AuthError):
    """当前操作需要有效登录态。"""


class CookieExpiredError(AuthRequiredError):
    """Cookie 已存在但远程平台确认登录态失效。"""


class CookieImportError(AuthError):
    """无法从指定来源导入 Cookie。"""


class CookieValidationError(AuthError):
    """Cookie 验证请求失败或返回了无效数据。"""


class CredentialStoreError(AuthError):
    """凭据存储无法读取、写入或通过完整性校验。"""


class InteractiveLoginError(AuthError):
    """交互式登录失败、取消或超时。"""
