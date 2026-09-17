/**
 * 本文件验证场景播放动作的结构、唯一性、资源引用和场景跳转关系。
 * 动作会被播放器直接执行，因此比普通展示字段具有更强的行为影响。验证器采用
 * 显式的类型分支，未知动作会被拒绝；动作时间还会结合场景预计时长检查，减少
 * 自动播放时永远无法触发的动作。
 */

import type { ValidationContext, ReportIssue } from "./internal.js";
import { isNonEmptyString, isObject } from "./internal.js";
import { validateAssetReference } from "./validate-references.js";

/** 验证一个场景中的全部播放动作。 */
export function validateActions(
  actions: unknown,
  path: string,
  estimatedDurationSeconds: number | undefined,
  context: ValidationContext,
  report: ReportIssue,
): void {
  if (actions === undefined) return;
  if (!Array.isArray(actions)) {
    report(path, "actions.type", "场景动作必须是数组。");
    return;
  }

  const actionIds = new Set<string>();
  actions.forEach((action, index) => {
    const actionPath = `${path}[${index}]`;
    if (!isObject(action)) {
      report(actionPath, "action.type", "播放动作必须是对象。");
      return;
    }

    if (!isNonEmptyString(action.id)) {
      report(`${actionPath}.id`, "action.id.required", "动作 ID 不能为空。");
    } else if (actionIds.has(action.id)) {
      report(`${actionPath}.id`, "action.id.duplicate", "同一场景内的动作 ID 不能重复。");
    } else {
      actionIds.add(action.id);
    }

    validateActionTime(action.atSeconds, actionPath, estimatedDurationSeconds, report);

    if (action.type === "pause") {
      if (typeof action.durationSeconds !== "number" || !Number.isFinite(action.durationSeconds) || action.durationSeconds < 0) {
        report(`${actionPath}.durationSeconds`, "action.pause.duration.invalid", "暂停时长必须是非负数。");
      }
    } else if (action.type === "narration") {
      if (!isNonEmptyString(action.text)) {
        report(`${actionPath}.text`, "action.narration.text.required", "旁白文本不能为空。");
      }
      if (action.audioAssetId !== undefined) {
        validateAssetReference(action.audioAssetId, "audio", `${actionPath}.audioAssetId`, context, report);
      }
    } else if (action.type === "go-to-scene") {
      if (!isNonEmptyString(action.targetSceneId) || !context.sceneIds.has(action.targetSceneId)) {
        report(`${actionPath}.targetSceneId`, "scene.missing", "动作引用的目标场景不存在。");
      }
    } else {
      report(`${actionPath}.type`, "action.type.unsupported", "当前版本不支持该动作类型。");
    }
  });
}

/** 验证动作触发时间，并在已知场景时长时检查动作是否会超出场景范围。 */
function validateActionTime(
  atSeconds: unknown,
  actionPath: string,
  estimatedDurationSeconds: number | undefined,
  report: ReportIssue,
): void {
  if (atSeconds === undefined) return;
  if (typeof atSeconds !== "number" || !Number.isFinite(atSeconds) || atSeconds < 0) {
    report(`${actionPath}.atSeconds`, "action.time.invalid", "动作触发时间必须是非负数。");
    return;
  }
  if (estimatedDurationSeconds !== undefined && atSeconds > estimatedDurationSeconds) {
    report(`${actionPath}.atSeconds`, "action.time.out_of_range", "动作触发时间不能超过场景预计时长。");
  }
}
