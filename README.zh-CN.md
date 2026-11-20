# BAT Agent

v0.6.1 · 内测版 · From BAT Team

本地代码工作台，界面默认英文。左侧文件和对话，中间代码编辑器，侧栏查看已注册 Skills。

- 模型对话、可选 API Key、已保存模型下拉选择。
- 文件读取、编辑、保存与冲突检查。
- Skill 创建、注册、读取，以及 Python/可选 Notebook 执行。
- 执行审批、结果查看、本地会话记录。
- 连接诊断、通信状态、模型等待时间和可用的上下文用量。

## 启动

已有正常使用且获准运行的项目环境时，保留原目录和 .venv，按 [现有环境中的源码更新](docs/existing-environment.md) 替换应用文件。

在更新后的源码目录打开 PowerShell，输入原来可用的 Python 完整路径，先检查依赖：

~~~powershell
$BatPython = Read-Host "Full path to the existing approved python.exe"
& $BatPython scripts/check_environment.py
~~~

报告 ok: true 后直接启动：

~~~powershell
& $BatPython -m agent_harness
~~~

打开 **http://127.0.0.1:8765**。终端保持运行，Ctrl+C 停止。依赖齐全时无需重新安装项目，也不新建环境。检查失败则先按 [安装说明](docs/setup.md) 处理；新环境只在需要且获准时创建。

运行工作台不需要 Node、npm 或下载浏览器。Python 依赖需已安装，或从允许使用的软件源安装。uv、离线安装和已有目录更新步骤见 [安装说明](docs/setup.md)。可以把 [COPILOT_SETUP.md](COPILOT_SETUP.md) 交给 Copilot 按步骤完成配置。

## 先看界面，再连接模型

连接页点击 **Open workspace without a model**，无需填写信息即可浏览、编辑文件并查看 Skills。

需要对话时，填写 Endpoint 和可选 API Key；点击 **Find models** 从列表选择。服务不提供列表时，填写管理员提供的模型名。点击 **Test connection** 实际验证，再进入工作台。错误提示会区分已观察到的 DNS、连接、TLS 或 HTTP 问题；不会把 403 直接判断成没有开 VPN。

回复采用异步返回，以段落、列表和代码块展示。**Show model reasoning** 只显示接口实际提供的内容。**Model time** 包含网络及服务端等待，不包含工具执行与审批。上下文数据未知时明确显示未知。

## 文档

[使用手册](docs/user-guide.md) · [安装与更新](docs/setup.md) · [连接排错](docs/connections.md) · [Skills](docs/skills.md) · [配置与 API](docs/configuration-api.md) · [启动检查](docs/deployment-checklist.md) · [安全边界](SECURITY.md)

服务限本机单用户使用。批准的脚本具有当前账户权限。模型配置、会话、私有 Skills 和工作区内容只保存在本地。
