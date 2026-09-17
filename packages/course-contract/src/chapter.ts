import type { CourseScene } from "./scene.js";

/** 课程中的一个有序章节。 */
export interface Chapter {
  /** 章节在课程文档中的唯一 ID。 */
  id: string;
  /** 向学习者展示的章节标题。 */
  title: string;
  /** 对章节内容和目标的简短说明。 */
  description?: string;
  /** 按默认学习顺序排列的场景。 */
  scenes: CourseScene[];
}
