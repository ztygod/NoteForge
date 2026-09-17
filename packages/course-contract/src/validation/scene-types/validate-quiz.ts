/**
 * 本文件验证单选题 payload 的业务完整性。除了检查题目和选项文本，还会构建选项
 * ID 集合来发现重复 ID，并确认 correctOptionId 确实指向一个可选择的选项。
 * 这些跨数组成员的关系无法仅依靠基础 JSON Schema 稳定表达。
 */

import type { ReportIssue } from "../internal.js";
import { isNonEmptyString, isObject } from "../internal.js";

/** 验证单选题场景的 payload。 */
export function validateSingleChoiceQuizPayload(
  payload: Record<string, unknown>,
  path: string,
  report: ReportIssue,
): void {
  if (!isNonEmptyString(payload.question)) {
    report(`${path}.question`, "quiz.question.required", "单选题题目不能为空。");
  }
  if (!Array.isArray(payload.options) || payload.options.length < 2) {
    report(`${path}.options`, "quiz.options.too_few", "单选题至少需要两个选项。");
    return;
  }

  const optionIds = new Set<string>();
  payload.options.forEach((option, index) => {
    const optionPath = `${path}.options[${index}]`;
    if (!isObject(option)) {
      report(optionPath, "quiz.option.type", "单选题选项必须是对象。");
      return;
    }
    if (!isNonEmptyString(option.id)) {
      report(`${optionPath}.id`, "quiz.option.id.required", "选项 ID 不能为空。");
    } else if (optionIds.has(option.id)) {
      report(`${optionPath}.id`, "quiz.option.id.duplicate", "单选题选项 ID 不能重复。");
    } else {
      optionIds.add(option.id);
    }
    if (!isNonEmptyString(option.text)) {
      report(`${optionPath}.text`, "quiz.option.text.required", "选项文本不能为空。");
    }
  });

  if (!isNonEmptyString(payload.correctOptionId) || !optionIds.has(payload.correctOptionId)) {
    report(`${path}.correctOptionId`, "quiz.answer.invalid", "正确答案必须对应一个已有选项。");
  }
}
