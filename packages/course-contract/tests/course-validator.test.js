import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { validateCourse } from "../dist/index.js";

const exampleUrl = new URL("../examples/minimal-course.json", import.meta.url);

test("最小课程示例能够通过验证", async () => {
  const course = JSON.parse(await readFile(exampleUrl, "utf8"));
  const result = validateCourse(course);
  assert.equal(result.success, true);
});

test("单选题答案必须引用已有选项", async () => {
  const course = JSON.parse(await readFile(exampleUrl, "utf8"));
  course.chapters[0].scenes[1].payload.correctOptionId = "missing";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "quiz.answer.invalid"));
});

test("来源引用必须指向已有来源", async () => {
  const course = JSON.parse(await readFile(exampleUrl, "utf8"));
  course.chapters[0].scenes[0].sourceRefs[0].sourceId = "missing";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "source.missing"));
});
