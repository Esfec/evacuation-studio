# 实时事件协议 v1

运行创建：POST /api/runs，JSON 正文为参数，可加 autoplay=false。返回 id。创建时完成参数与密钥必要性检查，之后在独立工作线程运行。密钥只保存在本次进程内存，运行结束清除引用。

实时订阅：GET /api/runs/{id}/events，标准 SSE。每条事件：

```json
{
  "protocol": "evacuation.events.v1",
  "run_id": "32位运行ID",
  "seq": 1,
  "type": "run.started",
  "step": 0,
  "timestamp": 1790000000.0,
  "data": {}
}
```

seq 在一场运行内从1单调递增，作为 SSE id。客户端去重；重连支持 Last-Event-ID 或 ?after=序号，不重启运行。墙钟时间用于观测网络耗时，不决定仿真推进。

| 事件 | 内容 / 时机 |
|---|---|
| run.started | 配置、实际拓扑、干预清单、来源、实现版本、有效画像与源码哈希 |
| snapshot | 初始帧及每个完整步结算后的自包含状态 |
| step.started | 开始新仿真步 |
| agent.observed | 决策前冻结的可见路径与状态/环境/路径记忆 |
| api.started | Agent、尝试序号、调用状态 |
| api.finished | 成功与否及延迟等调用信息 |
| agent.decided | 目标节点、决策模式、简短理由；此时尚未统一提交移动 |
| run.control | 控制动作及下一步边界生效约定 |
| run.ended | completed / cancelled / failed，valid、错误摘要 |

一次仿真步：更新灾害与后果 → 冻结输入 → 发出局部策略/并行API决策 → 等待整批决策完成 → 统一容量结算 → 提交位置 → snapshot。

请求返回顺序可以不同；它不触发提前移动。失败回退使用由 seed/step/agent 派生的随机源。引擎观察回调的异常单独记录，不修改研究状态。

POST /api/runs/{id}/control：正文 {"action":"pause|resume|step|stop"}。pause/stop 不取消已发出的外部请求，在本步完成后生效。step 放行一个完整步。

GET /api/runs/{id}/replay：evacuation.replay.v1，包含 config、settings、source、provenance、topology、snapshots、events、status、valid、fallback_count。快照包含 Agent 具名摘要与 context，不跨帧引用理由索引。

初始快照 step=-1、completed_steps=0。执行第一个步后 step=0、completed_steps=1，sim_time_s=completed_steps×step_seconds。动画只是两个已提交快照之间的路径插值。

每场运行目录实时追加 events.jsonl；结束时保存 replay.json、settings.json 和 research/ 日志。进程重启后可按运行 ID 读取已保存回放；内存中的未完成会话与 SSE 不会恢复执行。可导入已保存回放查看。

source=live_local 或 live_llm 表示记录的生成来源；打开录制不构成新API调用。旧交接包适配 source=archived、valid=null，缺少的观察字段明确显示未记录。

