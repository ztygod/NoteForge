import type { CourseDocument } from "../course.js";

/** 单个协议校验问题。 */
export interface ValidationIssue {
  /** 问题字段在输入对象中的路径。 */
  path: string;
  /** 便于程序识别和测试的稳定错误代码。 */
  code: string;
  /** 面向开发者说明问题原因的中文消息。 */
  message: string;
}

/** 课程文档验证成功的结果。 */
export interface ValidationSuccess {
  /** 表示输入通过全部验证。 */
  success: true;
  /** 通过验证并可按 CourseDocument 使用的输入数据。 */
  data: CourseDocument;
  /** 成功结果不包含任何问题。 */
  issues: [];
}

/** 课程文档验证失败的结果。 */
export interface ValidationFailure {
  /** 表示输入未通过验证。 */
  success: false;
  /** 失败结果中原始输入不会被当作 CourseDocument 返回。 */
  data?: never;
  /** 验证发现的全部问题。 */
  issues: ValidationIssue[];
}

/** 课程文档验证的联合返回类型。 */
export type ValidationResult = ValidationSuccess | ValidationFailure;
