/**
 * 本文件验证 slide 场景的专属 payload。第一版幻灯片采用按顺序排列的文档流元素，
 * 验证重点是元素类型、文本内容和图片资源引用。图片不仅必须存在，还必须声明为
 * image 类型，避免渲染器收到无法作为图片解码的资源。
 */

import type { ValidationContext, ReportIssue } from "../internal.js";
import { isNonEmptyString, isObject } from "../internal.js";
import { validateAssetReference } from "../validate-references.js";

/** 验证幻灯片场景的 payload。 */
export function validateSlidePayload(
  payload: Record<string, unknown>,
  path: string,
  context: ValidationContext,
  report: ReportIssue,
): void {
  if (!Array.isArray(payload.elements)) {
    report(`${path}.elements`, "slide.elements.type", "幻灯片元素必须是数组。");
    return;
  }

  payload.elements.forEach((element, index) => {
    const elementPath = `${path}.elements[${index}]`;
    if (!isObject(element)) {
      report(elementPath, "slide.element.type", "幻灯片元素必须是对象。");
      return;
    }
    if (element.type === "heading" || element.type === "paragraph") {
      if (!isNonEmptyString(element.text)) {
        report(`${elementPath}.text`, "slide.text.required", "幻灯片文本不能为空。");
      }
      if (element.type === "heading" && element.level !== undefined && ![1, 2, 3].includes(element.level as number)) {
        report(`${elementPath}.level`, "slide.heading.level.invalid", "标题层级必须是 1、2 或 3。");
      }
    } else if (element.type === "image") {
      validateAssetReference(element.assetId, "image", `${elementPath}.assetId`, context, report);
    } else {
      report(`${elementPath}.type`, "slide.element.unsupported", "当前版本不支持该幻灯片元素类型。");
    }
  });
}
