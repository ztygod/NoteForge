/**
 * 本文件是课程验证模块的公共导出入口。外部调用方只需要从这里获取 validateCourse
 * 和验证结果类型，内部上下文及各子验证器保持私有，从而避免业务代码绕过统一的
 *课程级验证流程。
 */

export * from "./validate-course.js";
export * from "./validation-result.js";
