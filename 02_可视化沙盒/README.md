# 栖木 · 建筑疏散观察室

新版启动、参数与测试说明见上一级 README.md、PARAMETERS.md、TEST_REPORT.md。

## 启动

在本目录执行：

```powershell
python -m pip install -r ../requirements-studio.txt
python live_server.py --port 8765
```

打开 http://127.0.0.1:8765 。新建运行使用实时本地引擎；LLM 策略需要密钥。
双击 疏散沙盒-单文件版.html 可离线查看30组录制，不发起API调用。

## 主要文件

- studio_server.py：标准库HTTP/SSE服务、参数校验与运行会话
- settings.py、run_cli.py：UI/CLI共用参数定义与命令行运行
- index.html、studio.css、studio.js、settings-ui.js：Canvas画面、观察面板、时间轴与配置
- studio_data.js：修复后实际执行的6组本地策略录制
- replay_data.js：交接包24组历史记录，界面标记为旧版
- build_demo.py：重新计算6组演示并嵌入完整字体
- bundle.py：生成单文件离线HTML
- tests/：会话/配置回归及Playwright浏览器检查
- runs/：按运行ID保存参数、事件、回放与研究CSV

参数示例：

```powershell
python run_cli.py --config ../evidence/ui-settings.json --output runs
python run_cli.py --help
```

密钥通过界面POST正文或环境变量传入，CLI使用 --api-key-env；不写入URL、参数文件或回放。
旧版 build_font.py / export_replay.py 为保留的历史辅助工具；当前使用完整原字体，直接导出新协议回放。
