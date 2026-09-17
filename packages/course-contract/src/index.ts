/**
 * 本文件定义 @noteforge/course-contract 唯一受支持的公共 API。所有导出均采用
 * 显式白名单，避免内部验证器、索引构建工具或目录调整意外成为兼容性承诺。
 * 外部模块只能从包根路径导入；新增公共能力时应在此处明确评估并导出。
 */

/** 验证未知输入是否为合法课程文档。 */
export { validateCourse } from "./validation/validate-course.js";

/** 当前课程协议版本及验证器支持的版本列表。 */
export { COURSE_SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS } from "./version.js";

export type {
  Action,
  ActionBase,
  GoToSceneAction,
  NarrationAction,
  PauseAction,
} from "./action.js";
export type { Asset, AssetType } from "./asset.js";
export type { Chapter } from "./chapter.js";
export type { CourseDocument } from "./course.js";
export type { CourseMetadata, SceneMetadata } from "./metadata.js";
export type {
  CourseScene,
  InteractiveScene,
  KnownScene,
  Scene,
  ScenePresentation,
  SingleChoiceQuizScene,
  SlideScene,
} from "./scene.js";
export type {
  InteractivePayload,
  SingleChoiceOption,
  SingleChoiceQuizPayload,
  SlideElement,
  SlideHeadingElement,
  SlideImageElement,
  SlideParagraphElement,
  SlidePayload,
} from "./scene-types/index.js";
export type { CourseSource, SourceReference, SourceType } from "./source.js";
export type {
  ValidationFailure,
  ValidationIssue,
  ValidationResult,
  ValidationSuccess,
} from "./validation/validation-result.js";
export type { SupportedSchemaVersion } from "./version.js";
