/**
 * 本文件保护 course-contract 的公共运行时 API 边界。测试明确确认根入口只暴露
 * 课程验证函数和版本常量，防止内部子验证器因为通配导出而被外部代码依赖。
 * 类型 API 由 TypeScript 严格编译负责校验，不会出现在 JavaScript 运行时对象中。
 */

import assert from "node:assert/strict";
import test from "node:test";

import * as contract from "../dist/index.js";

test("根入口只暴露稳定的运行时 API", () => {
  assert.deepEqual(Object.keys(contract).sort(), [
    "COURSE_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "validateCourse",
  ]);
});

test("内部验证工具不会从根入口暴露", () => {
  assert.equal("validateSlidePayload" in contract, false);
  assert.equal("validateAssetReference" in contract, false);
  assert.equal("createIssueCollector" in contract, false);
});
