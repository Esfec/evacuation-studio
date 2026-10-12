# 上传 GitHub

上传包包含仿真与前端完整源码、测试、内嵌演示、依赖清单与说明。所有新运行写入忽略目录，密钥模板为空。

## 方法一：网页上传

1. 在 GitHub 创建空仓库，例如 `evacuation-studio`。首次可设为 Private，按作者需要选择公开时间。
2. 解压 ZIP，进入里面的 `evacuation-studio` 文件夹。
3. 使用 Add file → Upload files 上传文件夹里的内容，使根目录直接出现 `README.md`、`start.py`、`01_研究源码/` 和 `02_可视化沙盒/`。
4. 确认根目录的 `.gitignore`、`.gitattributes`、`.env.example` 和 `.github/workflows/checks.yml` 也已上传；某些系统会隐藏点开头的文件。

文件数量较多时推荐方法二。ZIP 也可作为 Release 附件，但仅上传 ZIP 不会形成可浏览的源码仓库。

## 方法二：Git 推送

在解压后的 `evacuation-studio` 文件夹打开终端。先在 GitHub 创建空仓库，不初始化 README、许可证或 gitignore，再把以下占位地址换成自己的仓库地址：

```text
git init -b main
git add .
git status --short
git commit -m "Package evacuation simulation and museum pixel UI"
git remote add origin https://github.com/YOUR_ACCOUNT/evacuation-studio.git
git push -u origin main
```

GitHub 登录使用 Git Credential Manager、SSH 或访问令牌，避免把令牌写入仓库地址或文件。若已有同名远程仓库，请合并到其正常开发流程，不要强制覆盖历史。

根目录 `LICENSE_STATUS.md` 如实说明源码许可尚未指定；GitHub 创建仓库时可以暂不选择许可证。字体自带 OFL 1.1。作者确定源码许可后再加入正式 `LICENSE`。

## 包内内容

- 与当前工作版本一致的仿真和前端代码。
- 内嵌的 6 组本地规则录制和 24 组来源项目历史录制。
- 来源项目的紧凑研究汇总与图表，标识为历史材料。
- 最新两轮真实 DeepSeek 的审计摘要与质量问题说明。

本地完整运行目录、当前服务进程、虚拟环境、`node_modules`、Git 历史、密钥文件和私有协作说明没有包含。新运行可按 README 自行生成，完整历史原始数据需要另行授权整理。
