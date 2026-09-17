/** 交互场景的专属内容。 */
export interface InteractivePayload {
  /** 交互内容的加载方式。 */
  mode: "url" | "html";
  /** mode 为 url 时加载的页面地址。 */
  url?: string;
  /** mode 为 html 时在受限 iframe 中加载的 HTML。 */
  html?: string;
  /** 向学习者说明如何操作交互内容的文字。 */
  instructions?: string;
}
