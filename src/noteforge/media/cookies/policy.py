"""平台 Cookie 最小权限策略。"""

from dataclasses import dataclass

from noteforge.media.models import VideoPlatform


@dataclass(frozen=True, slots=True)
class CookiePolicy:
    """平台固定域名白名单，调用方不能自行扩大范围。"""

    platform: VideoPlatform
    allowed_domains: tuple[str, ...]  # 允许根域及其子域。

    def allows(self, domain: str) -> bool:
        """执行标签边界匹配，避免伪造后缀域名通过检查。"""

        value = domain.lstrip(".").casefold()
        return any(
            value == allowed.lstrip(".").casefold()
            or value.endswith("." + allowed.lstrip(".").casefold())
            for allowed in self.allowed_domains
        )


POLICIES = {
    VideoPlatform.YOUTUBE: CookiePolicy(
        VideoPlatform.YOUTUBE,
        ("youtube.com", "googlevideo.com", "youtu.be"),
    ),
    VideoPlatform.BILIBILI: CookiePolicy(
        VideoPlatform.BILIBILI,
        ("bilibili.com",),
    ),
}


def policy_for(platform: VideoPlatform | str) -> CookiePolicy:
    """返回内置平台策略；未知平台直接拒绝。"""

    return POLICIES[VideoPlatform(platform)]
