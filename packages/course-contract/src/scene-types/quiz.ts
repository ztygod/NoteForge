/** 单选题的一个选项。 */
export interface SingleChoiceOption {
  /** 选项在当前题目中的唯一 ID。 */
  id: string;
  /** 向学习者展示的选项文本。 */
  text: string;
}

/** 单选题场景的专属内容。 */
export interface SingleChoiceQuizPayload {
  /** 向学习者展示的问题。 */
  question: string;
  /** 可供选择的选项，至少应包含两个。 */
  options: SingleChoiceOption[];
  /** 正确选项的 ID，必须对应 options 中的一个选项。 */
  correctOptionId: string;
  /** 学习者提交答案后展示的解释。 */
  explanation?: string;
}
