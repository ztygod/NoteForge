/** 课程资源支持的媒体类型。 */
export type AssetType = "image" | "audio" | "video" | "file";

/** 课程引用的外部或后端托管资源。 */
export interface Asset {
  /** 资源类别，用于决定加载和展示方式。 */
  type: AssetType;
  /** 资源访问地址，可以是 API 路径或完整 URL。 */
  uri: string;
  /** 资源的 MIME 类型，例如 image/png。 */
  mimeType: string;
  /** 无障碍展示或资源不可用时使用的替代文本。 */
  alt?: string;
  /** 资源文件大小，单位为字节。 */
  sizeBytes?: number;
}
