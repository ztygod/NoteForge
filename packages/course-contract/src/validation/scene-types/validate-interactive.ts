/**
 * 本文件验证 interactive 场景的加载模式与基础安全边界。HTML 静态检查只能拦截
 * 明显危险内容，不能替代浏览器隔离；因此这里拒绝脚本标签、内联事件和 JavaScript
 * URL，同时要求 Renderer 始终使用不含 allow-same-origin 的 sandbox iframe。
 */

import type { ReportIssue } from "../internal.js";
import { isNonEmptyString } from "../internal.js";

const MAX_HTML_LENGTH = 256 * 1024;
const DANGEROUS_HTML_PATTERNS = [
  /<script\b/i,
  /\son[a-z]+\s*=/i,
  /javascript\s*:/i,
  /<iframe\b/i,
  /<object\b/i,
  /<embed\b/i,
];

/** 验证交互场景的 payload。 */
export function validateInteractivePayload(
  payload: Record<string, unknown>,
  path: string,
  report: ReportIssue,
): void {
  if (payload.mode === "url") {
    if (!isNonEmptyString(payload.url)) {
      report(`${path}.url`, "interactive.url.required", "URL 交互内容必须提供地址。");
    } else if (!isSafeInteractiveUrl(payload.url)) {
      report(`${path}.url`, "interactive.url.unsafe", "交互地址必须使用 HTTPS、HTTP 或站内相对路径。");
    }
    return;
  }

  if (payload.mode === "html") {
    if (!isNonEmptyString(payload.html)) {
      report(`${path}.html`, "interactive.html.required", "HTML 交互内容必须提供 HTML。");
    } else {
      if (payload.html.length > MAX_HTML_LENGTH) {
        report(`${path}.html`, "interactive.html.too_large", "HTML 交互内容不能超过 256 KiB。");
      }
      if (DANGEROUS_HTML_PATTERNS.some((pattern) => pattern.test(payload.html as string))) {
        report(`${path}.html`, "interactive.html.unsafe", "HTML 交互内容包含不允许的可执行或嵌套标签。");
      }
    }
    return;
  }

  report(`${path}.mode`, "interactive.mode.invalid", "交互内容模式必须是 url 或 html。");
}

/** 只允许常规 Web 地址和站内相对地址，明确拒绝 data/javascript 等协议。 */
function isSafeInteractiveUrl(value: string): boolean {
  if (value.startsWith("/")) return !value.startsWith("//");
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}
