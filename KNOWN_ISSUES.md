# 当前版本已知问题

## DeepSeek 目标字段与重试（studio-1.5 已修复协议，待真实重跑）

2026-10-12 两轮真实 DeepSeek 运行中，部分响应把 `target_id` 填成“过厅”等房间名，导致 N06 轮 17 次、N01 轮 12 次无效输出及 4 / 2 次规则兜底，两轮均为 `quality=degraded`。

studio-1.5-llm-protocol 的处理（见 CHANGELOG）：

- 系统提示明确 `target_id` 必须填写节点 ID。
- 目标解析只在 Agent 本步可选方向内做确定性匹配：精确 ID；大小写/空白（`id_case`）；字符串内恰好一个可选 ID（`id_in_text`）；恰好一个可选方向的房间名（`name`）。歧义、非可选方向或未知值仍为 `invalid_target`。每次匹配方式写入 `llm_call_log.target_normalization`，回放附 `llm_protocol` 汇总。
- 无效输出的重试会附上模型上一条回复和一条协议纠正（指出错误字段并重列允许 ID），记为 `feedback_retry`；不提供新的环境事实。

这些修改只用接口替身测试过（单元 9 项 + 端到端 2 轮模拟），**尚未用真实 API 重跑**。2026-10-12 的两轮记录和正式实验数据未改写，仍按原协议解释。正式实验应在新协议下重跑，并分别报告 LLM 采纳、名称规范化、纠错重试、恐慌覆盖和规则兜底。

## 旧资料与版本

`01_研究源码/docs/RELEASE_REVIEW.md`、部分研究 README 和历史图表描述的是来源项目先前的版本；当前机制说明以根目录 `FINAL_MECHANISM_AUDIT.md`、`MECHANISM_AUDIT.md` 和变更记录为准。原始历史付费日志没有包含，依赖它们的测试会跳过。

`02_可视化沙盒/tests/browser.cjs` 是早期完整交互测试，部分气泡文案断言已过期。新版使用 `visual-context.cjs`、`building-layout.cjs` 和 `effects-browser.cjs` 检查当前气泡、布局与特效。

## 模型与服务

服务面向本地使用，默认仅监听 `127.0.0.1`。火烟与行为参数未经过真实消防工程或人群实验校准；真实模型名称、权限和 API 行为取决于服务商账号。本次打包验证使用本地策略和接口替身，没有重新发起付费请求。
