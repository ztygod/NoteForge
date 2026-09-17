/** 当前课程文档协议版本。 */
export const COURSE_SCHEMA_VERSION = "1.0" as const;

/** 当前验证器能够识别的课程文档协议版本列表。 */
export const SUPPORTED_SCHEMA_VERSIONS = [COURSE_SCHEMA_VERSION] as const;

/** 当前支持的课程文档协议版本。 */
export type SupportedSchemaVersion = (typeof SUPPORTED_SCHEMA_VERSIONS)[number];
