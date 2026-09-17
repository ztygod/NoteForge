/**
 * 本文件是 CourseDocument 运行时验证的唯一公共入口。它先检查课程顶层结构并建立
 * assets、sources、sceneIds 等课程级索引，再把场景内容、动作和引用规则委派给
 * 独立验证器。两阶段设计保证跳转动作可以引用文档中后出现的场景，同时让所有
 * 子验证器共享一致的上下文并一次性返回尽可能完整的问题列表。
 */

import type { Asset } from "../asset.js";
import type { CourseDocument } from "../course.js";
import type { CourseSource } from "../source.js";
import { SUPPORTED_SCHEMA_VERSIONS } from "../version.js";
import { createIssueCollector, isNonEmptyString, isObject } from "./internal.js";
import type { ValidationContext } from "./internal.js";
import { validateInteractivePayload } from "./scene-types/validate-interactive.js";
import { validateSingleChoiceQuizPayload } from "./scene-types/validate-quiz.js";
import { validateSlidePayload } from "./scene-types/validate-slide.js";
import { validateActions } from "./validate-action.js";
import { validateAssetReference, validateSourceReferences } from "./validate-references.js";
import type { ValidationResult } from "./validation-result.js";

const SUPPORTED_SCENE_VERSIONS: Record<string, readonly string[]> = {
  slide: ["1.0"],
  "quiz.single-choice": ["1.0"],
  interactive: ["1.0"],
};

type Report = ReturnType<typeof createIssueCollector>["report"];

/** 验证未知输入是否为结构和语义均合法的 CourseDocument。 */
export function validateCourse(input: unknown): ValidationResult {
  const { issues, report } = createIssueCollector();
  if (!isObject(input)) {
    return { success: false, issues: [{ path: "$", code: "document.type", message: "课程文档必须是对象。" }] };
  }

  if (!SUPPORTED_SCHEMA_VERSIONS.includes(input.schemaVersion as "1.0")) {
    report("schemaVersion", "schema.unsupported", "课程协议版本不受支持。");
  }
  if (!isNonEmptyString(input.id)) report("id", "id.required", "课程 ID 不能为空。");

  validateMetadata(input.metadata, report);
  const assets = validateAssets(input.assets, report);
  const sources = validateSources(input.sources, report);
  const sceneIds = collectDocumentIds(input, report);
  const context: ValidationContext = { assets, sources, sceneIds };

  if (isObject(input.metadata) && input.metadata.coverAssetId !== undefined) {
    validateAssetReference(input.metadata.coverAssetId, "image", "metadata.coverAssetId", context, report);
  }
  validateChapters(input.chapters, context, report);

  return issues.length === 0
    ? { success: true, data: input as unknown as CourseDocument, issues: [] }
    : { success: false, issues };
}

/** 验证课程元数据中影响展示和追踪的基础字段。 */
function validateMetadata(metadata: unknown, report: Report): void {
  if (!isObject(metadata)) {
    report("metadata", "metadata.required", "课程元数据必须是对象。");
    return;
  }
  if (!isNonEmptyString(metadata.title)) report("metadata.title", "title.required", "课程标题不能为空。");
  if (!isNonEmptyString(metadata.language)) report("metadata.language", "language.required", "课程语言不能为空。");
  validateIsoDate(metadata.createdAt, "metadata.createdAt", true, report);
  validateIsoDate(metadata.updatedAt, "metadata.updatedAt", false, report);
}

/** 验证 ISO 时间；可选字段不存在时不产生错误。 */
function validateIsoDate(value: unknown, path: string, required: boolean, report: Report): void {
  if (value === undefined && !required) return;
  if (!isNonEmptyString(value) || Number.isNaN(Date.parse(value))) {
    report(path, "date.invalid", "时间必须是有效的 ISO 8601 字符串。");
  }
}

/** 验证资源表自身结构并返回可供交叉引用检查使用的索引。 */
function validateAssets(value: unknown, report: Report): Record<string, Asset> {
  if (!isObject(value)) {
    report("assets", "assets.type", "课程资源表必须是对象。");
    return {};
  }
  for (const [id, asset] of Object.entries(value)) {
    const path = `assets.${id}`;
    if (!isObject(asset)) {
      report(path, "asset.type", "资源必须是对象。");
      continue;
    }
    if (!["image", "audio", "video", "file"].includes(asset.type as string)) {
      report(`${path}.type`, "asset.kind.invalid", "资源类型不受支持。");
    }
    if (!isNonEmptyString(asset.uri)) report(`${path}.uri`, "asset.uri.required", "资源地址不能为空。");
    if (!isNonEmptyString(asset.mimeType)) report(`${path}.mimeType`, "asset.mime.required", "资源 MIME 类型不能为空。");
    if (asset.sizeBytes !== undefined && (!Number.isInteger(asset.sizeBytes) || (asset.sizeBytes as number) < 0)) {
      report(`${path}.sizeBytes`, "asset.size.invalid", "资源大小必须是非负整数。");
    }
  }
  return value as Record<string, Asset>;
}

/** 验证来源表自身结构并返回可供场景引用检查使用的索引。 */
function validateSources(value: unknown, report: Report): Record<string, CourseSource> {
  if (!isObject(value)) {
    report("sources", "sources.type", "课程来源表必须是对象。");
    return {};
  }
  for (const [id, source] of Object.entries(value)) {
    const path = `sources.${id}`;
    if (!isObject(source)) {
      report(path, "source.type", "课程来源必须是对象。");
      continue;
    }
    if (!["video", "audio", "document", "webpage"].includes(source.type as string)) {
      report(`${path}.type`, "source.kind.invalid", "来源类型不受支持。");
    }
    if (!isNonEmptyString(source.uri)) report(`${path}.uri`, "source.uri.required", "来源地址不能为空。");
  }
  return value as Record<string, CourseSource>;
}

/** 第一遍遍历收集课程、章节、场景 ID，使动作可引用后续场景。 */
function collectDocumentIds(input: Record<string, unknown>, report: Report): Set<string> {
  const allIds = new Set<string>();
  const sceneIds = new Set<string>();
  if (isNonEmptyString(input.id)) allIds.add(input.id);
  if (!Array.isArray(input.chapters)) {
    report("chapters", "chapters.type", "课程章节必须是数组。");
    return sceneIds;
  }

  input.chapters.forEach((chapter, chapterIndex) => {
    if (!isObject(chapter)) return;
    addUniqueId(chapter.id, `chapters[${chapterIndex}].id`, "章节", allIds, report);
    if (!Array.isArray(chapter.scenes)) return;
    chapter.scenes.forEach((scene, sceneIndex) => {
      if (!isObject(scene)) return;
      addUniqueId(scene.id, `chapters[${chapterIndex}].scenes[${sceneIndex}].id`, "场景", allIds, report);
      if (isNonEmptyString(scene.id)) sceneIds.add(scene.id);
    });
  });
  return sceneIds;
}

/** 将 ID 加入课程级索引，并报告空值或跨层级重复。 */
function addUniqueId(value: unknown, path: string, label: string, ids: Set<string>, report: Report): void {
  if (!isNonEmptyString(value)) report(path, "id.required", `${label} ID 不能为空。`);
  else if (ids.has(value)) report(path, "id.duplicate", `${label} ID 必须在课程中唯一。`);
  else ids.add(value);
}

/** 第二遍遍历验证章节和场景的内容、动作及引用。 */
function validateChapters(chapters: unknown, context: ValidationContext, report: Report): void {
  if (!Array.isArray(chapters)) return;
  chapters.forEach((chapter, chapterIndex) => {
    const chapterPath = `chapters[${chapterIndex}]`;
    if (!isObject(chapter)) {
      report(chapterPath, "chapter.type", "章节必须是对象。");
      return;
    }
    if (!isNonEmptyString(chapter.title)) report(`${chapterPath}.title`, "title.required", "章节标题不能为空。");
    if (!Array.isArray(chapter.scenes)) {
      report(`${chapterPath}.scenes`, "scenes.type", "章节场景必须是数组。");
      return;
    }
    chapter.scenes.forEach((scene, sceneIndex) => validateScene(scene, `${chapterPath}.scenes[${sceneIndex}]`, context, report));
  });
}

/** 验证场景公共外壳，并按 kind 分派到专属 payload 验证器。 */
function validateScene(scene: unknown, path: string, context: ValidationContext, report: Report): void {
  if (!isObject(scene)) {
    report(path, "scene.type", "场景必须是对象。");
    return;
  }
  if (!isNonEmptyString(scene.kind) || !(scene.kind in SUPPORTED_SCENE_VERSIONS)) {
    report(`${path}.kind`, "kind.unsupported", "当前版本不支持该场景类型。");
    return;
  }
  if (!isNonEmptyString(scene.kindVersion) || !SUPPORTED_SCENE_VERSIONS[scene.kind]?.includes(scene.kindVersion)) {
    report(`${path}.kindVersion`, "kind.version.unsupported", "当前场景类型版本不受支持。");
  }
  if (!isObject(scene.payload)) {
    report(`${path}.payload`, "payload.type", "场景内容必须是对象。");
    return;
  }

  if (scene.kind === "slide") validateSlidePayload(scene.payload, `${path}.payload`, context, report);
  else if (scene.kind === "quiz.single-choice") validateSingleChoiceQuizPayload(scene.payload, `${path}.payload`, report);
  else validateInteractivePayload(scene.payload, `${path}.payload`, report);

  validateSourceReferences(scene.sourceRefs, `${path}.sourceRefs`, context, report);
  const duration = isObject(scene.metadata) && typeof scene.metadata.estimatedDurationSeconds === "number"
    ? scene.metadata.estimatedDurationSeconds
    : undefined;
  if (duration !== undefined && (!Number.isFinite(duration) || duration < 0)) {
    report(`${path}.metadata.estimatedDurationSeconds`, "scene.duration.invalid", "场景预计时长必须是非负数。");
  }
  validateActions(scene.actions, `${path}.actions`, duration, context, report);
}
