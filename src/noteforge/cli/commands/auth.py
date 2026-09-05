"""认证生命周期 CLI 命令。"""

import sys
from pathlib import Path

import typer

from noteforge.auth import AuthError, AuthManager, AuthPlatform, AuthStatus

app = typer.Typer(help="管理 Bilibili 和 YouTube 登录态。", no_args_is_help=True)


def _platform(value: str) -> AuthPlatform:
    try:
        return AuthPlatform(value.casefold())
    except ValueError as error:
        raise typer.BadParameter("平台必须是 bilibili 或 youtube。") from error


@app.command("login")
def login(
    source: str | None = typer.Argument(
        None, help="Cookie JSON 路径，或与 --raw 配合使用的 Cookie 文本。"
    ),
    platform: str = typer.Option(
        "bilibili", "--platform", help="认证平台：bilibili 或 youtube。"
    ),
    browser: str | None = typer.Option(
        None, "--browser", help="指定浏览器；默认自动发现。"
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="把位置参数作为 Cookie Header 解析（可能进入 shell history）。",
    ),
    raw_stdin: bool = typer.Option(
        False, "--raw-stdin", help="从标准输入安全读取 Cookie Header。"
    ),
    qr: bool = typer.Option(False, "--qr", help="打开可见浏览器完成交互登录。"),
    timeout: int = typer.Option(180, "--timeout", min=10, help="交互登录超时秒数。"),
) -> None:
    """从浏览器、JSON、文本或交互窗口导入并加密保存 Cookie。"""

    selected = _platform(platform)
    modes = sum((source is not None, raw_stdin, qr))
    if modes > 1 or (raw and source is None):
        raise typer.BadParameter("JSON、raw、stdin 和 QR 登录方式不能同时使用。")
    manager = AuthManager()
    try:
        if qr:
            result = manager.login_interactively(selected, timeout=timeout)
        elif raw_stdin:
            result = manager.login_from_raw(selected, sys.stdin.read().strip())
        elif source is not None and raw:
            typer.secho(
                "警告：命令行 Cookie 可能被 shell history 记录，推荐使用 --raw-stdin。",
                fg=typer.colors.YELLOW,
                err=True,
            )
            result = manager.login_from_raw(selected, source)
        elif source is not None:
            result = manager.login_from_json(selected, Path(source))
        else:
            typer.echo("正在检查本机浏览器登录态...")
            result = manager.login_from_browser(selected, browser=browser)
    except AuthError as error:
        typer.secho(f"认证失败：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
    detail = f"（{result.browser}）" if result.browser else ""
    typer.secho(f"✓ {selected.value} 登录状态验证成功{detail}", fg=typer.colors.GREEN)
    typer.secho("✓ Cookie 已加密保存", fg=typer.colors.GREEN)


@app.command("status")
def status(
    platform: str | None = typer.Option(
        None, "--platform", help="只检查 bilibili 或 youtube。"
    ),
) -> None:
    """检查已保存 Cookie 的真实登录状态。"""

    platforms = (_platform(platform),) if platform else tuple(AuthPlatform)
    manager = AuthManager()
    failed = False
    for selected in platforms:
        try:
            result = manager.status(selected)
        except AuthError as error:
            typer.secho(
                f"{selected.value:<10} validation error  {error}", fg=typer.colors.RED
            )
            failed = True
            continue
        label = {
            AuthStatus.AUTHENTICATED: "authenticated",
            AuthStatus.COOKIE_EXPIRED: "cookie expired",
            AuthStatus.NO_COOKIE: "no cookie",
            AuthStatus.MISSING_REQUIRED_FIELDS: "missing fields",
            AuthStatus.IMPORT_FAILED: "import failed",
        }[result.status]
        refreshed = (
            result.refreshed_at.strftime("%Y-%m-%d %H:%M")
            if result.refreshed_at
            else "-"
        )
        typer.echo(
            f"{selected.value:<10} {label:<18} {result.browser or '-':<10} {refreshed}"
        )
    if failed:
        raise typer.Exit(code=1)


@app.command("logout")
def logout(
    platform: str = typer.Option(
        "bilibili", "--platform", help="清除 bilibili 或 youtube 凭据。"
    ),
) -> None:
    """删除 NoteForge 加密凭据，不修改浏览器登录态。"""

    selected = _platform(platform)
    AuthManager().logout(selected)
    typer.echo(f"已清除 {selected.value} 的 NoteForge 凭据。")
