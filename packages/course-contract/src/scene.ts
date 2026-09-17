import type { Action } from "./action.js";
import type { SceneMetadata } from "./metadata.js";
import type { SourceReference } from "./source.js";
import type {
  InteractivePayload,
  SingleChoiceQuizPayload,
  SlidePayload,
} from "./scene-types/index.js";

/** 场景通用展示配置。 */
export interface ScenePresentation {
  /** 场景使用的主题标识，由渲染器解释。 */
  theme?: string;
  /** 场景切换方式，manual 表示用户切换，auto 表示自动切换。 */
  navigation?: "manual" | "auto";
  /** 学习者是否允许跳过当前场景。 */
  skippable?: boolean;
}

/** 所有场景共享的稳定外壳。 */
export interface Scene<TKind extends string, TPayload> {
  /** 场景在课程文档中的唯一 ID。 */
  id: string;
  /** 场景内容类型，用于选择内容验证器和渲染器。 */
  kind: TKind;
  /** 当前场景 payload 所遵循的类型协议版本。 */
  kindVersion: string;
  /** 场景的标题、说明和预计时长等信息。 */
  metadata?: SceneMetadata;
  /** 当前场景引用的原始材料位置。 */
  sourceRefs?: SourceReference[];
  /** 当前场景通用的展示和导航设置。 */
  presentation?: ScenePresentation;
  /** 场景播放过程中按顺序执行的动作。 */
  actions?: Action[];
  /** 由 kind 和 kindVersion 决定结构的场景专属内容。 */
  payload: TPayload;
}

/** 幻灯片场景。 */
export type SlideScene = Scene<"slide", SlidePayload>;

/** 单选题场景。 */
export type SingleChoiceQuizScene = Scene<
  "quiz.single-choice",
  SingleChoiceQuizPayload
>;

/** 交互内容场景。 */
export type InteractiveScene = Scene<"interactive", InteractivePayload>;

/** 第一版协议明确支持的场景联合类型。 */
export type KnownScene = SlideScene | SingleChoiceQuizScene | InteractiveScene;

/** 用于接收并检查尚未验证的扩展场景，不属于有效 CourseDocument。 */
export type UnknownScene = Scene<string, unknown>;

/** 课程文档当前允许包含的场景。 */
export type CourseScene = KnownScene;
