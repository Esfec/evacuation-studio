# 参数与复现

UI“新建运行”和 run_cli.py 使用同一服务校验及 RunConfig。可以导出/导入完整 JSON。API Key 不进入配置文件。

## 可设置项

| UI 设置 | JSON / CLI | 默认 / 范围 |
|---|---|---|
| 策略 | policy / --policy | Local_Rule；另有 Global_ShortestPath、RiskAware_Dijkstra、Random、Mock_Heterogeneous、LLM_Agent |
| 建筑方案 | design / --design | D0、D1、D2 |
| 初始关闭条件 | condition / --condition | C0 开放、C1 关闭 N10 |
| 种子 | seed / --seed | 42；0–2147483647 |
| 最大步数 | steps / --steps | 30；1–300 |
| 三类人数 | cognitive、perceptual、follower / 同名旗标 | 10 / 15 / 23；每类0–100，总数1–120 |
| 起火节点 | fire_origin / --fire-origin | N01；非出口且未被条件关闭的节点 |
| 火灾传播率 | fire_rate / --fire-rate | 0.1；0.01–1，越大越快 |
| 烟雾传播率 | smoke_rate / --smoke-rate | null；UI 留空随火灾，否则0.01–1 |
| 烟雾强度系数 | smoke_scale / --smoke-scale | 0.9；0–1 |
| 风险时序系数 | risky_coeff / --risky-coeff | 3；0.1–30 |
| 封闭延迟系数 | blocked_coeff / --blocked-coeff | 7；0.1–60 |
| 通道服务容量 | base_edge_capacity / --base-edge-capacity | 4；1–100 人/方向/步 |
| 标称步长 | step_seconds / --step-seconds | 5；1–60秒，仅时间标签 |
| 自动起点最少跳数 | min_hops_to_exit / --min-hops-to-exit | 3；1–18 |
| 风险/人群权重 | risk_weight、crowd_weight / --risk-weight、--crowd-weight | 6 / 2；0–100，仅风险感知策略使用 |
| 服务商、模型 | provider、model / --provider、--model | OpenAI / gpt-4o；候选来自原 config.py |
| 温度 | temperature / --temperature | 0.1；0–2 |
| API 并发 | concurrency / --concurrency | 8；1–32 |
| 画像 | agent_profiles / --profile-file | 完整 Agent.json 结构 |
| 逐 Agent 位置 | initial_positions / --positions-file | Agent ID→房间 ID |
| 房间人数分布 | initial_distribution / --distribution-file | 房间 ID→人数 |

各服务商对温度等参数的支持可能不同；无效模型响应按原 API 层错误策略记录。

## 初始位置

三种方式互斥：

- 自动：按种子、人数、当前拓扑、起点距离筛选；候选不足时保留原有 2 跳/1 跳降级规则；排除原模型禁用起点并检查容量。
- 按房间：人数之和必须等于三类总数；类型在这些位置上的分配受种子控制。
- 逐个：必须完整覆盖当前人数对应的全部 ID，精确保留每个 ID 的节点。

ID 使用原模型的全局序号。例如认知2人、感知1人、跟随1人得到 C01、C02、P03、F04，并非每类从01重新计数。更改人数后需重新核对分配。

手动位置允许起火房间及死端，不接受出口、关闭节点、不存在节点或初始超容量。手动方式不使用自动起点跳数限制。

例：

```json
{
  "cognitive": 2,
  "perceptual": 1,
  "follower": 1,
  "initial_positions": {
    "C01": "N01",
    "C02": "N03",
    "P03": "N04",
    "F04": "N17"
  },
  "fire_origin": "N06",
  "fire_rate": 0.08,
  "smoke_rate": 0.12,
  "seed": 42,
  "steps": 30
}
```

## 火与烟的具体含义

设 h 为起火点到节点的无向拓扑最短跳数，k=0.1/fire_rate：

- 非起火普通节点：风险步数=max(1, round(h×risky_coeff×k))。
- 封闭步数=风险步数+max(1, round(h×blocked_coeff×k))。
- 起火点：从第0步有风险，max(2, round(5×k))步封闭。
- 出口不生成火灾时序，场景关闭节点从开始即不可通行。

风险在时间阈值之间分段上升。烟雾默认沿用相同时序，在封闭前乘 smoke_scale，达到自身封闭时刻后饱和至1。新增 smoke_rate 可独立调整烟雾时序；null 保留原来的火烟同步。即使 smoke_scale=0，饱和时刻仍为1；该系数不是“关闭烟雾”开关。

这些规则依据拓扑跳数，不使用房间真实距离、材料、通风、热释放率或物理扩散方程。独立烟雾参数属于新增模型扩展；研究使用时应在实验方法中说明。

## 三类画像

UI 编辑三类画像的13项：行动概率系数、初始体力、每步体力消耗、恐慌阈值、压力抵抗、动作扰动概率、忽略出口概率、跟随人群偏向、高/低能见度发现概率、感知噪声、路径记忆长度、允许折返。JSON 导入还保留画像描述等完整结构。

画像不是人的真实测量特征；修改后产生新的研究条件。完整有效画像随 settings.json 保存并计算 SHA256。原画像锁文件保持其既有内容和哈希。

## 固定模型与可配置参数的区别

本次 UI 配置针对已有18节点研究模型。任意绘制平面、增加节点、逐门编辑几何、多个起火源，以及物理火灾模型不在当前引擎的支持范围内。D0/D1/D2 为固定设计干预：D1 将 N06↔N10 容量翻倍，D2 增加 N06↔N08 连接；C1 关闭 N10。不能用视觉拖动或动画改变这些研究规则。

## 复现

同一代码/地图/有效画像、同一参数及种子下，本地策略逐步状态可复现。保存 settings.json、replay.json、events.jsonl、research/ 和源码版本。回放记录源码/地图/画像哈希。

运行时间、UUID、事件墙钟时间不要求一致。真实 LLM 受外部模型及网络行为影响，不承诺复跑逐步一致。对照面板只比较有效完成且除 design 外配置及哈希相同的记录；单一种子不构成统计推断。

