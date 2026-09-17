/** 原始材料支持的来源类型。 */
export type SourceType = "video" | "audio" | "document" | "webpage";

/** 生成课程时使用的原始材料。 */
export interface CourseSource {
  /** 原始材料类别。 */
  type: SourceType;
  /** 原始材料的展示名称。 */
  title?: string;
  /** 原始材料地址，例如视频链接或文档资源地址。 */
  uri: string;
}

/** 场景内容在原始材料中的可追溯位置。 */
export interface SourceReference {
  /** 被引用来源的 ID，必须指向 sources 中的来源。 */
  sourceId: string;
  /** 引用片段的开始时间，单位为秒，仅用于时序媒体。 */
  startSeconds?: number;
  /** 引用片段的结束时间，单位为秒，仅用于时序媒体。 */
  endSeconds?: number;
  /** 文档页码，仅用于分页文档。 */
  page?: number;
  /** 对引用内容或引用理由的补充说明。 */
  note?: string;
}
