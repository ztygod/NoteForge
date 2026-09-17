/**
 * 本文件覆盖 CourseDocument 增强验证器的核心语义规则。测试通过复制同一份合法示例
 * 并制造单一错误，确保每条规则返回稳定的错误代码；这些错误代码会被后端生成修复
 * 流程和前端诊断界面消费，因此属于需要保持兼容的公共行为。
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { validateCourse } from "../dist/index.js";

const exampleUrl = new URL("../examples/minimal-course.json", import.meta.url);

async function loadExample() {
  return JSON.parse(await readFile(exampleUrl, "utf8"));
}

test("最小课程示例能够通过验证", async () => {
  const course = await loadExample();
  const result = validateCourse(course);
  assert.equal(result.success, true);
});

test("单选题答案必须引用已有选项", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[1].payload.correctOptionId = "missing";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "quiz.answer.invalid"));
});

test("来源引用必须指向已有来源", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[0].sourceRefs[0].sourceId = "missing";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "source.missing"));
});

test("章节和场景 ID 不能与课程 ID 重复", async () => {
  const course = await loadExample();
  course.chapters[0].id = course.id;
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "id.duplicate"));
});

test("单选题选项 ID 不能重复", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[1].payload.options[1].id = "a";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "quiz.option.id.duplicate"));
});

test("图片元素必须引用图片资源", async () => {
  const course = await loadExample();
  course.assets.audio = { type: "audio", uri: "/audio.mp3", mimeType: "audio/mpeg" };
  course.chapters[0].scenes[0].payload.elements.push({ type: "image", assetId: "audio" });
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "asset.type.invalid"));
});

test("动作 ID 不可重复且跳转目标必须存在", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[0].actions = [
    { id: "next", type: "go-to-scene", targetSceneId: "missing" },
    { id: "next", type: "pause", durationSeconds: 1 }
  ];
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "scene.missing"));
  assert.ok(result.issues.some((issue) => issue.code === "action.id.duplicate"));
});

test("旁白音频必须引用音频资源", async () => {
  const course = await loadExample();
  course.assets.picture = { type: "image", uri: "/image.png", mimeType: "image/png" };
  course.chapters[0].scenes[0].actions = [
    { id: "speak", type: "narration", text: "欢迎学习", audioAssetId: "picture" }
  ];
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "asset.type.invalid"));
});

test("场景类型版本必须受支持", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[0].kindVersion = "2.0";
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "kind.version.unsupported"));
});

test("动作时间不能超过场景预计时长", async () => {
  const course = await loadExample();
  course.chapters[0].scenes[0].metadata.estimatedDurationSeconds = 10;
  course.chapters[0].scenes[0].actions = [
    { id: "late", type: "pause", atSeconds: 11, durationSeconds: 1 }
  ];
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "action.time.out_of_range"));
});

test("HTML 交互内容拒绝明显危险标签", async () => {
  const course = await loadExample();
  course.chapters[0].scenes.push({
    id: "scene-interactive",
    kind: "interactive",
    kindVersion: "1.0",
    payload: { mode: "html", html: "<button onclick=\"alert(1)\">运行</button>" }
  });
  const result = validateCourse(course);
  assert.equal(result.success, false);
  assert.ok(result.issues.some((issue) => issue.code === "interactive.html.unsafe"));
});
