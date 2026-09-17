/** 课程级元数据。 */
export interface CourseMetadata {
  /** 面向学习者展示的课程标题。 */
  title: string;
  /** 对课程内容和学习目标的简短说明。 */
  description?: string;
  /** 课程主要语言，建议使用 BCP 47 标记，例如 zh-CN。 */
  language: string;
  /** 作为课程封面的资源 ID，必须指向 assets 中的资源。 */
  coverAssetId?: string;
  /** 课程文档创建时间，使用 ISO 8601 格式。 */
  createdAt: string;
  /** 课程文档最后更新时间，使用 ISO 8601 格式。 */
  updatedAt?: string;
}

/** 场景级元数据。 */
export interface SceneMetadata {
  /** 面向学习者展示的场景标题。 */
  title?: string;
  /** 对当前场景内容的简短说明。 */
  description?: string;
  /** 预计完成当前场景所需的秒数。 */
  estimatedDurationSeconds?: number;
}
