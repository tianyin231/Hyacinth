---
name: excelsorf-continuity
description: Use when working in the ExcelSorf repository on requirements, design, implementation, testing, review, release, progress reporting, or resuming work after context loss or a new session.
---

# 风信子项目接续

## 核心原则

以磁盘中的项目事实接续工作，不依赖聊天记忆。任何影响需求、范围、进度、阻塞、验证结果或下一步的变化，都必须在回复用户前写入 `references/project-state.yaml`。

**只在最终回复中总结不算完成状态更新。上下文压缩、时间紧迫或用户催促都不是跳过更新的理由。**

## 每次任务开始

1. 完整读取 `references/project-state.yaml`。
2. 读取状态文件指向的需求来源，以及当前任务直接相关的代码和测试。
3. 检查实际目录、Git 状态和可用验证环境；不得照抄旧状态而不核实。
4. 按以下优先级解决冲突：
   - 用户最新明确决定；
   - 实际代码、测试和命令输出；
   - `需求讨论记录.md` 中已确认需求；
   - `references/project-state.yaml` 中的执行状态；
   - `软件前端框架设计.md` 原始需求。
5. 如果资料仍不足以安全实施，只询问一个会改变方案的关键问题，并把阻塞写入状态。

## 状态边界

| 信息 | 唯一位置 | 规则 |
|---|---|---|
| 当前有效需求 | `需求讨论记录.md` | 用户确认变更后立即更新；保留被取代决定的引用 |
| 原始客户输入 | `软件前端框架设计.md` | 只作为原始证据，不随实施状态改写 |
| 当前进度与接续点 | `references/project-state.yaml` | 持续替换为最新事实，避免另建 `HANDOFF.md` |
| 实现行为 | 源码与测试 | 以可重复验证结果为准 |

不要把实现状态、测试结果或临时接续点写进需求正文。不要创建第二份项目状态文档。

## 即时更新触发器

发生以下任一事件后，先更新状态，再继续可能消耗大量上下文的工作：

- 用户确认、修改、撤销或推翻需求；
- 阶段、任务或里程碑状态变化；
- 发现新阻塞、风险、假设或外部依赖；
- 完成可独立验收的实现或修复；
- 得到新的测试、性能、截图或打包证据；
- 即将压缩上下文、切换会话、暂停或结束任务。

不要为每次普通文件编辑制造状态噪声。只记录会影响下一位执行者判断的信息。

## 需求变更

1. 先复述新规则及受影响范围；存在歧义时先确认。
2. 更新 `需求讨论记录.md` 的对应章节。旧决定不得无痕删除，使用“已被 `<decision_id>` 取代”保留追溯。
3. 在 `project-state.yaml` 的 `recent_decisions` 中记录：`id`、`date`、`status`、`summary`、`source`、`supersedes`、`impact`。
4. 更新当前任务、下一步和需要新增或修改的测试。
5. 再开始实现。

`recent_decisions` 只保留最近 10 条；更早决定保留在需求记录和 Git 历史中。

## 代理路线

Codex/Sol 是唯一规划者、调度者、审查者和集成者。

- 需要子代理、并行调查、独立实现或复核时，必须使用 `sol-ds-control` 管理的 OpenCode Worker。
- 当前指定 Worker 为 `opencode-go/deepseek-v4-flash`。
- 不使用 Codex 内置子代理替代该路线。
- 给 Worker 明确 `Task ID`、绝对工作目录、写入范围、禁止项、输入、预期结果和验证方式。
- 独立只读任务可并行；共享接口和公共文件由 Codex/Sol 串行集成。
- 当前目录没有 Git 隔离时，同时最多允许一个写入 Worker。
- Worker 的成功声明不是证据；Codex/Sol 必须检查实际文件并重新运行最终验证。

## 回复用户前

1. 运行与本次变更成比例的验证。
2. 更新 `project-state.yaml`：
   - `updated_at`；
   - `current_phase`；
   - `current_task`；
   - `last_completed`；
   - `next_actions`；
   - `blockers`；
   - `changed_files`；
   - `verification`。
3. 运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/excelsorf-continuity/scripts/validate-state.ps1 -RequireFreshMinutes 30
```

4. 校验失败时修正状态，不得声称任务完成。
5. 最终回复只简要说明结果、验证和下一步，不依赖回复承担跨会话接续。

## 基线失败与约束

| 常见做法 | 必须改为 |
|---|---|
| 临时创建 `HANDOFF.md` | 只更新 `project-state.yaml` |
| 把实现进度写进需求章节 | 需求与执行状态分离 |
| 任意选择可用子代理 | 只走 Sol + OpenCode DeepSeek |
| 测试通过后直接回复 | 先更新状态并校验新鲜度 |
| 依赖聊天历史接续 | 从磁盘事实重建上下文 |

## 当前项目路线

当前采用“风险原型 + 垂直切片 + 阶段验收”。完整状态、已确认技术方向和下一步读取 `references/project-state.yaml`，不得在本文件重复维护。
