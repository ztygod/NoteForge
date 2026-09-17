# `@noteforge/course-contract`

NoteForge 课程数据的纯协议包。它定义课程文档、章节、场景、动作、资源、来源和首批场景类型，并提供无框架依赖的运行时验证器。

该包不负责课程生成、React 渲染、持久化、用户学习状态或版本迁移。

```ts
import { validateCourse, type CourseDocument } from "@noteforge/course-contract";

const result = validateCourse(input);
if (result.success) {
  const course: CourseDocument = result.data;
}
```

当前内置场景类型为 `slide`、`quiz.single-choice` 和 `interactive`。JSON Schema 位于 `schemas/`，有效示例位于 `examples/`。
