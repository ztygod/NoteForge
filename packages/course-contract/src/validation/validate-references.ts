/**
 * 本文件验证 CourseDocument 中跨对象的引用关系，包括来源时间范围和资源类型。
 * JSON Schema 能判断 assetId/sourceId 是字符串，却无法判断对应对象是否真实存在，
 * 因此这些规则集中在这里实现。资源验证同时检查实际媒体类型，防止播放器把音频
 * 当图片使用，或把普通文件作为旁白播放。
 */

import type { AssetType } from "../asset.js";
import type { ValidationContext, ReportIssue } from "./internal.js";
import { isNonEmptyString, isObject } from "./internal.js";

/** 验证一个资源 ID 存在且类型符合使用场景。 */
export function validateAssetReference(
  assetId: unknown,
  expectedType: AssetType,
  path: string,
  context: ValidationContext,
  report: ReportIssue,
): void {
  if (!isNonEmptyString(assetId) || !(assetId in context.assets)) {
    report(path, "asset.missing", "引用的资源不存在。");
    return;
  }

  if (context.assets[assetId]?.type !== expectedType) {
    report(path, "asset.type.invalid", `该字段必须引用 ${expectedType} 类型资源。`);
  }
}

/** 验证场景中的全部来源引用及其时间、页码范围。 */
export function validateSourceReferences(
  references: unknown,
  path: string,
  context: ValidationContext,
  report: ReportIssue,
): void {
  if (references === undefined) return;
  if (!Array.isArray(references)) {
    report(path, "sourceRefs.type", "来源引用必须是数组。");
    return;
  }

  references.forEach((reference, index) => {
    const referencePath = `${path}[${index}]`;
    if (!isObject(reference)) {
      report(referencePath, "sourceRef.type", "来源引用必须是对象。");
      return;
    }

    if (!isNonEmptyString(reference.sourceId) || !(reference.sourceId in context.sources)) {
      report(`${referencePath}.sourceId`, "source.missing", "场景引用的来源不存在。");
    }

    // 时间允许使用小数秒，但不能为负数，也不能出现结束时间早于开始时间。
    const start = reference.startSeconds;
    const end = reference.endSeconds;
    if (start !== undefined && (typeof start !== "number" || !Number.isFinite(start) || start < 0)) {
      report(`${referencePath}.startSeconds`, "source.time.invalid", "来源开始时间必须是非负数。");
    }
    if (end !== undefined && (typeof end !== "number" || !Number.isFinite(end) || end < 0)) {
      report(`${referencePath}.endSeconds`, "source.time.invalid", "来源结束时间必须是非负数。");
    }
    if (typeof start === "number" && typeof end === "number" && end < start) {
      report(`${referencePath}.endSeconds`, "source.range.invalid", "来源结束时间不能早于开始时间。");
    }

    if (reference.page !== undefined && (!Number.isInteger(reference.page) || (reference.page as number) < 1)) {
      report(`${referencePath}.page`, "source.page.invalid", "来源页码必须是从 1 开始的整数。");
    }
  });
}
