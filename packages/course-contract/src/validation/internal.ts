/**
 * 本文件提供验证器内部共享的上下文、错误收集器和基础类型判断函数。
 * 设计上将“如何记录问题”和“具体检查什么”分离，使场景、动作和引用验证器
 * 可以保持短小，并使用完全一致的路径与错误格式。本文件不是公共 API，调用方
 * 应始终通过 validateCourse 进入验证流程。
 */

import type { Asset } from "../asset.js";
import type { CourseSource } from "../source.js";
import type { ValidationIssue } from "./validation-result.js";

/** 语义验证所需的课程级索引。 */
export interface ValidationContext {
  /** 课程中已声明的全部资源。 */
  assets: Record<string, Asset>;
  /** 课程中已声明的全部来源。 */
  sources: Record<string, CourseSource>;
  /** 课程中全部合法场景 ID。 */
  sceneIds: Set<string>;
}

/** 统一收集验证问题的函数签名。 */
export type ReportIssue = (path: string, code: string, message: string) => void;

/** 判断未知值是否为普通对象。 */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** 判断未知值是否为非空字符串。 */
export function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** 创建统一的问题收集器，避免各子验证器自行拼装返回结果。 */
export function createIssueCollector(): {
  /** 当前已经收集的问题。 */
  issues: ValidationIssue[];
  /** 向结果中追加一个结构化问题。 */
  report: ReportIssue;
} {
  const issues: ValidationIssue[] = [];
  return {
    issues,
    report: (path, code, message) => issues.push({ path, code, message }),
  };
}
