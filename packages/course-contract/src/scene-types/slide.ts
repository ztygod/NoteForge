/** 幻灯片中的标题元素。 */
export interface SlideHeadingElement {
  /** 固定的标题元素类型。 */
  type: "heading";
  /** 标题文字。 */
  text: string;
  /** 标题层级，1 为最高层级。 */
  level?: 1 | 2 | 3;
}

/** 幻灯片中的正文元素。 */
export interface SlideParagraphElement {
  /** 固定的正文元素类型。 */
  type: "paragraph";
  /** 正文文字。 */
  text: string;
}

/** 幻灯片中的图片元素。 */
export interface SlideImageElement {
  /** 固定的图片元素类型。 */
  type: "image";
  /** 图片资源 ID，必须指向课程 assets 中的资源。 */
  assetId: string;
  /** 图片的无障碍替代文本。 */
  alt?: string;
  /** 图片下方展示的说明文字。 */
  caption?: string;
}

/** 第一版幻灯片支持的内容元素。 */
export type SlideElement =
  | SlideHeadingElement
  | SlideParagraphElement
  | SlideImageElement;

/** 幻灯片场景的专属内容。 */
export interface SlidePayload {
  /** 按展示顺序排列的幻灯片内容元素。 */
  elements: SlideElement[];
}
