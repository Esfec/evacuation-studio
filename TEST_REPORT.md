# 测试与交付核验

最新机制审查（1.3）：核心 115 passed / 2 skipped；服务 29 passed。另完成 18 次本地运行、14,928 条 Agent 逐步状态不变量检查；证据见 evidence/final-mechanism-audit.json。此前章节为各阶段留档。

测试实施：2026-10-11；交付核验：2026-10-12。环境：Windows、Python 3.12.3，Playwright Chromium。

## 已执行结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 研究核心全部测试 | 104 passed，2 skipped | evidence/core-tests.txt |
| 实时服务与参数回归 | 27 passed | evidence/service-tests.txt |
| 浏览器交互与视觉检查 | 24 checks passed，0 JS errors | evidence/browser-tests.json |
| UI配置导出→CLI独立执行 | 初始帧+3步，4帧状态全部一致 | evidence/ui-cli-parity.json |
| 新演示来源检查 | 6组真实本地运行，核心/地图/画像哈希匹配 | evidence/example-provenance.json |

两项跳过源于交接包没有分发完整付费模型审计数据，不是已验证的外部API调用。研究测试有两个依赖警告：protobuf日期API弃用、Streamlit缓存协程未await；未影响断言通过，原始输出保留。

## 核心验证内容

- 18节点、D0/D1/D2与C0/C1、退出状态、灾害阈值、信息可见性及日志契约。
- 满员链式阻塞、交换/环路、300组随机容量不变量与输入顺序无关性。
- 本地固定种子快照一致；独立Python进程不同PYTHONHASHSEED下相同。
- 并行调用完成前不提交移动；回退随机数不受返回顺序影响。
- 精确放置、房间分配、参数往返、独立烟雾及默认兼容。
- 缺密钥、非法节点、初始超容、不完整ID、非法参数拒绝。
- 暂停/步进/停止、事件单调序号、SSE续接、异常运行、落盘及密钥不进入回放。

## 浏览器检查内容

1920×1080与1440×810无整页溢出；研究/展示模式；Agent选择及四类上下文气泡；本地真实运行单步/恢复；参数传到引擎；配置导出；导出/导入回放；同条件比较；离线单文件；所有画面通路为正交且不穿入无关房间。

截图：

- evidence/research-1920x1080.png
- evidence/presentation-1920x1080.png
- evidence/research-1440x810.png
- evidence/D2-C1-bubbles.png
- evidence/parameter-editor.png

UI/CLI一致性比较包含全部Agent、节点、边、计数和决策上下文，仅忽略每步实测 wall_seconds；不要求运行UUID与事件墙钟一致。

## 复验命令

在交付根目录：

```powershell
python -m pip install -r 01_研究源码/requirements.txt
cd 01_研究源码
python -m pytest tests -q
cd ../02_可视化沙盒
python -m pytest tests -q
```

浏览器测试需要本地服务运行在8765。在第二个终端：

```powershell
cd 02_可视化沙盒
npm install
npx playwright install chromium
node tests/browser.cjs
```

日常启动和命令行仿真不需要Node或浏览器测试依赖。测试会新增一场4人本地运行并更新evidence截图。

## 验证边界

本轮机制修复未再发起付费 LLM 调用。用户此前的真实 DeepSeek 运行已单独审计并原样保留；自动化 API 替身只用于时序和错误回归，未写入6组演示数据。既有24组历史录制未重新计算。

仿真仍是拓扑、离散步模型。代码正确性检查与演示运行不能替代实测疏散标定、消防工程验证、多种子统计实验。


## DeepSeek修复后的追加验证

完整核心回归96通过、2跳过、2个既有依赖警告；完整服务回归27通过。之后新增决策CSV聚合回归，与DeepSeek请求模式测试一起执行2项均通过。原运行的22帧完整性检查零异常，导入真实回放的界面降级标识和对照排除检查通过。证据：evidence/deepseek-audit/。

## studio-1.2 机制修复追加验证

- 核心完整回归：104 passed，2 skipped；服务完整回归：27 passed。
- 浏览器：24 checks passed，0 JS errors；1920×1080 截图底部显示 `studio-1.2-spatial-memory-flow`。
- 新增回归覆盖：感知为空时的真实门洞兜底、关闭路线不恢复、连接记忆、实际流量跟随、等待资历优先、Mock 出口识别、完成时刻、终止数值下限、移动健康字段。
- 同配置本地复验中 N04 的 `NO_VISIBLE_PATHS` 从用户旧运行的 36 次降为 0；该复验使用 Local_Rule，只证明机制修复，不作为 DeepSeek 效果实验。
- 证据：`evidence/core-tests.txt`、`evidence/service-tests.txt`、`evidence/browser-tests.json`、`evidence/mechanism-validation/`。
