import type { Asset } from "./asset.js";
import type { Chapter } from "./chapter.js";
import type { CourseMetadata } from "./metadata.js";
import type { CourseSource } from "./source.js";
import type { SupportedSchemaVersion } from "./version.js";

/** 一门可展示、可验证且可追溯的 NoteForge 课程。 */
export interface CourseDocument {
  /** 当前文档遵循的课程协议版本。 */
  schemaVersion: SupportedSchemaVersion;
  /** 课程文档的全局唯一 ID。 */
  id: string;
  /** 课程标题、语言和创建时间等基础信息。 */
  metadata: CourseMetadata;
  /** 按默认学习顺序排列的课程章节。 */
  chapters: Chapter[];
  /** 以资源 ID 为键的课程媒体资源表。 */
  assets: Record<string, Asset>;
  /** 以来源 ID 为键的原始材料表。 */
  sources: Record<string, CourseSource>;
}
