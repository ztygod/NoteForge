/** 所有播放动作共同拥有的字段。 */
export interface ActionBase {
  /** 动作在当前场景内的唯一 ID。 */
  id: string;
  /** 动作类型，用于选择对应的动作执行器。 */
  type: string;
  /** 动作相对场景开始的触发时间，单位为秒。 */
  atSeconds?: number;
}

/** 让播放器等待指定时长的动作。 */
export interface PauseAction extends ActionBase {
  /** 固定的暂停动作类型。 */
  type: "pause";
  /** 暂停持续时间，单位为秒。 */
  durationSeconds: number;
}

/** 播放旁白文本的动作。 */
export interface NarrationAction extends ActionBase {
  /** 固定的旁白动作类型。 */
  type: "narration";
  /** 需要朗读或显示的旁白文本。 */
  text: string;
  /** 可选的音频资源 ID，存在时优先播放预生成音频。 */
  audioAssetId?: string;
}

/** 跳转到另一个场景的动作。 */
export interface GoToSceneAction extends ActionBase {
  /** 固定的场景跳转动作类型。 */
  type: "go-to-scene";
  /** 目标场景 ID。 */
  targetSceneId: string;
}

/** 第一版协议内置支持的播放动作。 */
export type Action = PauseAction | NarrationAction | GoToSceneAction;
