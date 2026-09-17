import type { CourseDocument } from "../course.js";
import { SUPPORTED_SCHEMA_VERSIONS } from "../version.js";
import type { ValidationIssue, ValidationResult } from "./validation-result.js";

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const nonEmpty = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;

/** 验证未知输入是否为合法的 CourseDocument。 */
export function validateCourse(input: unknown): ValidationResult {
  const issues: ValidationIssue[] = [];
  const issue = (path: string, code: string, message: string): void => {
    issues.push({ path, code, message });
  };

  if (!object(input)) {
    return {
      success: false,
      issues: [{ path: "$", code: "document.type", message: "课程文档必须是对象。" }],
    };
  }

  if (!SUPPORTED_SCHEMA_VERSIONS.includes(input.schemaVersion as "1.0")) {
    issue("schemaVersion", "schema.unsupported", "课程协议版本不受支持。");
  }
  if (!nonEmpty(input.id)) issue("id", "id.required", "课程 ID 不能为空。");

  if (!object(input.metadata)) {
    issue("metadata", "metadata.required", "课程元数据必须是对象。");
  } else {
    if (!nonEmpty(input.metadata.title)) issue("metadata.title", "title.required", "课程标题不能为空。");
    if (!nonEmpty(input.metadata.language)) issue("metadata.language", "language.required", "课程语言不能为空。");
    if (!nonEmpty(input.metadata.createdAt) || Number.isNaN(Date.parse(input.metadata.createdAt as string))) {
      issue("metadata.createdAt", "date.invalid", "课程创建时间必须是 ISO 8601 时间。");
    }
  }

  const assets = object(input.assets) ? input.assets : {};
  const sources = object(input.sources) ? input.sources : {};
  if (!object(input.assets)) issue("assets", "assets.type", "课程资源表必须是对象。");
  if (!object(input.sources)) issue("sources", "sources.type", "课程来源表必须是对象。");

  const ids = new Set<string>();
  const sceneIds = new Set<string>();
  if (!Array.isArray(input.chapters)) {
    issue("chapters", "chapters.type", "课程章节必须是数组。");
  } else {
    input.chapters.forEach((chapter, chapterIndex) => {
      const chapterPath = `chapters[${chapterIndex}]`;
      if (!object(chapter)) {
        issue(chapterPath, "chapter.type", "章节必须是对象。");
        return;
      }
      validateId(chapter.id, `${chapterPath}.id`, "章节", ids, issue);
      if (!nonEmpty(chapter.title)) issue(`${chapterPath}.title`, "title.required", "章节标题不能为空。");
      if (!Array.isArray(chapter.scenes)) {
        issue(`${chapterPath}.scenes`, "scenes.type", "章节场景必须是数组。");
        return;
      }
      chapter.scenes.forEach((scene, sceneIndex) => {
        const scenePath = `${chapterPath}.scenes[${sceneIndex}]`;
        if (!object(scene)) {
          issue(scenePath, "scene.type", "场景必须是对象。");
          return;
        }
        validateId(scene.id, `${scenePath}.id`, "场景", ids, issue);
        if (nonEmpty(scene.id)) sceneIds.add(scene.id);
        if (!nonEmpty(scene.kind)) issue(`${scenePath}.kind`, "kind.required", "场景类型不能为空。");
        if (!nonEmpty(scene.kindVersion)) issue(`${scenePath}.kindVersion`, "kind.version.required", "场景类型版本不能为空。");
        validateScenePayload(scene, scenePath, assets, issue);
        validateReferences(scene, scenePath, sources, issue);
      });
    });
  }

  if (object(input.metadata) && nonEmpty(input.metadata.coverAssetId) && !(input.metadata.coverAssetId in assets)) {
    issue("metadata.coverAssetId", "asset.missing", "课程封面引用的资源不存在。");
  }

  if (Array.isArray(input.chapters)) {
    input.chapters.forEach((chapter, ci) => {
      if (!object(chapter) || !Array.isArray(chapter.scenes)) return;
      chapter.scenes.forEach((scene, si) => {
        if (!object(scene) || !Array.isArray(scene.actions)) return;
        scene.actions.forEach((action, ai) => {
          if (object(action) && action.type === "go-to-scene" && (!nonEmpty(action.targetSceneId) || !sceneIds.has(action.targetSceneId))) {
            issue(`chapters[${ci}].scenes[${si}].actions[${ai}].targetSceneId`, "scene.missing", "动作引用的目标场景不存在。");
          }
        });
      });
    });
  }

  return issues.length === 0
    ? { success: true, data: input as unknown as CourseDocument, issues: [] }
    : { success: false, issues };
}

function validateId(
  value: unknown,
  path: string,
  label: string,
  ids: Set<string>,
  issue: (path: string, code: string, message: string) => void,
): void {
  if (!nonEmpty(value)) return issue(path, "id.required", `${label} ID 不能为空。`);
  if (ids.has(value)) issue(path, "id.duplicate", `${label} ID 必须在课程中唯一。`);
  ids.add(value);
}

function validateReferences(
  scene: Record<string, unknown>,
  path: string,
  sources: Record<string, unknown>,
  issue: (path: string, code: string, message: string) => void,
): void {
  if (!Array.isArray(scene.sourceRefs)) return;
  scene.sourceRefs.forEach((reference, index) => {
    if (!object(reference)) return issue(`${path}.sourceRefs[${index}]`, "sourceRef.type", "来源引用必须是对象。");
    if (!nonEmpty(reference.sourceId) || !(reference.sourceId in sources)) {
      issue(`${path}.sourceRefs[${index}].sourceId`, "source.missing", "场景引用的来源不存在。");
    }
    if (typeof reference.startSeconds === "number" && typeof reference.endSeconds === "number" && reference.endSeconds < reference.startSeconds) {
      issue(`${path}.sourceRefs[${index}].endSeconds`, "source.range.invalid", "来源结束时间不能早于开始时间。");
    }
  });
}

function validateScenePayload(
  scene: Record<string, unknown>,
  path: string,
  assets: Record<string, unknown>,
  issue: (path: string, code: string, message: string) => void,
): void {
  if (!object(scene.payload)) return issue(`${path}.payload`, "payload.type", "场景内容必须是对象。");
  const payload = scene.payload;
  if (scene.kind !== "slide" && scene.kind !== "quiz.single-choice" && scene.kind !== "interactive") {
    issue(`${path}.kind`, "kind.unsupported", "当前版本不支持该场景类型。");
    return;
  }
  if (scene.kind === "slide") {
    if (!Array.isArray(payload.elements)) return issue(`${path}.payload.elements`, "slide.elements.type", "幻灯片元素必须是数组。");
    payload.elements.forEach((element, index) => {
      if (object(element) && element.type === "image" && (!nonEmpty(element.assetId) || !(element.assetId in assets))) {
        issue(`${path}.payload.elements[${index}].assetId`, "asset.missing", "图片元素引用的资源不存在。");
      }
    });
  }
  if (scene.kind === "quiz.single-choice") {
    if (!nonEmpty(payload.question)) issue(`${path}.payload.question`, "quiz.question.required", "单选题题目不能为空。");
    if (!Array.isArray(payload.options) || payload.options.length < 2) {
      issue(`${path}.payload.options`, "quiz.options.too_few", "单选题至少需要两个选项。");
    } else {
      const optionIds = new Set(payload.options.filter(object).map((option) => option.id).filter(nonEmpty));
      if (!nonEmpty(payload.correctOptionId) || !optionIds.has(payload.correctOptionId)) {
        issue(`${path}.payload.correctOptionId`, "quiz.answer.invalid", "正确答案必须对应一个已有选项。");
      }
    }
  }
  if (scene.kind === "interactive") {
    if (payload.mode === "url" && !nonEmpty(payload.url)) issue(`${path}.payload.url`, "interactive.url.required", "URL 交互内容必须提供地址。");
    else if (payload.mode === "html" && !nonEmpty(payload.html)) issue(`${path}.payload.html`, "interactive.html.required", "HTML 交互内容必须提供 HTML。");
    else if (payload.mode !== "url" && payload.mode !== "html") issue(`${path}.payload.mode`, "interactive.mode.invalid", "交互内容模式必须是 url 或 html。");
  }
}
