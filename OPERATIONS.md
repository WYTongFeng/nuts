# Nuts 本地版完整操作手册

适用版本：本地第二版，2026-10-23。中文界面，英文检测与润色，在自己的电脑运行。

仓库：[WYTongFeng/nuts](https://github.com/WYTongFeng/nuts)。网站运行在本机，不是 GitHub 上的在线服务。

## 目录

1. [从 GitHub 获取项目](#1-从-github-获取项目)
2. [Windows 首次安装](#2-windows-首次安装)
3. [安装本地润色模型](#3-安装本地润色模型)
4. [每次启动和关闭](#4-每次启动和关闭)
5. [英文检测怎么用](#5-英文检测怎么用)
6. [英文润色怎么用](#6-英文润色怎么用)
7. [记录四个平台的实测成绩](#7-记录四个平台的实测成绩)
8. [保存结果和实验数据](#8-保存结果和实验数据)
9. [macOS 和 Linux](#9-macos-和-linux)
10. [更新项目和换电脑](#10-更新项目和换电脑)
11. [故障排查](#11-故障排查)
12. [开发、测试和提交 GitHub](#12-开发测试和提交-github)
13. [文件导航与当前限制](#13-文件导航与当前限制)

## 1. 从 GitHub 获取项目

### 方式 A：下载 ZIP，不需要 Git

1. 打开 [项目主页](https://github.com/WYTongFeng/nuts)。
2. 点击绿色 **Code** 按钮，选择 **Download ZIP**。
3. 完整解压到一个普通文件夹，例如 `C:\Projects\nuts`。不要在 ZIP 压缩包里面直接运行脚本。
4. 打开文件夹，确认看到 `setup.bat`、`start.bat`、`server.py`、`model.json`。

GitHub 下载的文件夹可能叫 `nuts-main`，名字不影响运行。ZIP 里不包含 Python 环境和大模型，下一步会在这台电脑重新安装。

### 方式 B：使用 Git，方便以后更新

先安装 [Git](https://git-scm.com/downloads)，在 PowerShell 里进入你希望存放项目的父目录，然后运行：

```powershell
git clone https://github.com/WYTongFeng/nuts.git
cd nuts
```

`git clone` 只在第一次使用；以后按第 10 节更新。

## 2. Windows 首次安装

### 需要准备

- Python 3.12，安装程序来自 [Python 官网](https://www.python.org/downloads/windows/)。
- Python 安装时保留 **Python Launcher**，勾选 **Add Python to PATH**。
- 第一次安装 Python 依赖、GPT-2 和 Ollama 模型需要网络及足够磁盘空间。
- Node.js 不是运行网站的必要条件，只用于开发时的 JS 一致性测试。

在新的 PowerShell 窗口检查：

```powershell
py -3.12 --version
```

应显示 `Python 3.12.x`。

### 双击安装

进入项目文件夹，双击 `setup.bat`。

它会：

1. 在当前项目建立 `.venv` Python 虚拟环境。
2. 安装 `requirements.txt` 中的检测依赖。
3. 成功后显示 `Setup complete`。

安装中请等窗口完成，不要提前关掉。若报错，阅读第 11 节；脚本不会替你安装 Python 或 Ollama。

### 手动安装（双击失败时）

在项目文件夹打开 PowerShell，依次运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

不需要先执行 `Activate.ps1`，因此无需为了激活虚拟环境修改 PowerShell 执行策略。

首次英文检测会下载 GPT-2（约 500MB），之后使用本机缓存。若下载或依赖失败，网页可以切换到规则检测，并明确显示降级状态。

## 3. 安装本地润色模型

检测和润色使用不同模型。仅安装 Python 依赖不会自动获得润色能力。

1. 从 [Ollama 官网](https://ollama.com/download) 安装并启动 Ollama。
2. 重新打开 PowerShell，运行：

   ```powershell
   ollama --version
   ollama pull qwen2.5:7b
   ollama list
   ```

3. 等待下载完成，确认列表中有 `qwen2.5:7b`。
4. 在 Nuts 的“英文润色”页点击“刷新连接”，选择该模型。

[qwen2.5:7b 官方页面](https://ollama.com/library/qwen2.5:7b)列出的模型文件约 4.7GB。实际运行还需要额外内存，速度取决于机器和文本长度。

若运行吃力，可以试用小模型：

```powershell
ollama pull qwen2.5:1.5b
```

然后刷新页面中的模型列表。小模型通常更省资源，但内容保留和改写质量仍需自己检查。

### 本地模式

Nuts 固定连接 `http://127.0.0.1:11434`，不提供远程地址配置，模型列表会过滤带云标记的模型。可进一步关闭 Ollama 云功能：

1. Windows 搜索“编辑账户的环境变量”。
2. 新增用户变量：名称 `OLLAMA_NO_CLOUD`，值 `1`。
3. 完全退出 Ollama，再从开始菜单重新启动。

详见 [Ollama 官方说明](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)。此步骤不是给程序配置 API Key，项目不需要付费 API Key。

## 4. 每次启动和关闭

### 启动

1. 要润色时，先确保 Ollama 在运行。
2. 双击 `start.bat`。
3. 浏览器自动打开本机页面。通常是 `http://localhost:8000`；如果端口被占用，程序会在 8001–8010 中寻找可用端口，以终端显示的地址为准。
4. 运行期间保留终端窗口。

不自动打开浏览器的启动方式：

```powershell
.\.venv\Scripts\python.exe server.py --no-browser
```

然后手动打开终端显示的地址。

### 关闭

先保存需要的结果，在运行服务的终端按 `Ctrl+C`。关闭浏览器标签页不等于关闭后台服务。

程序只监听本机 `127.0.0.1`，默认不能让另一台电脑通过局域网访问。换电脑时应在另一台电脑安装一份。

## 5. 英文检测怎么用

1. 选择“英文检测”。
2. 粘贴英文，或点击“导入 TXT”。
3. 至少输入 80 个英文词，每次最多 2,000 词、20,000 字符。
4. 点击“检测文本”，也可以在输入框中按 `Ctrl+Enter`（Mac 为 `Cmd+Enter`）。
5. 查看右侧的分数、判断依据和句子列表。
6. 点击列出的句子可定位原文；可以开关原文高亮。

结果显示 **GPT-2 + 规则** 时为完整检测；显示 **仅规则 · 降级模式** 时为备用检测。两种引擎的分数可能不同。

修改输入后，已有结果会变灰，需重新检测。分数是模型判断倾向，不是“文章有多少百分比由 AI 写成”，也不是作者身份的证明。

## 6. 英文润色怎么用

1. 选择“英文润色”，确认已连接本地模型。
2. 粘贴原文或导入 TXT。
3. 选择风格：
   - **自然流畅**：调整表达，使句子更自然清楚。
   - **简洁清晰**：减少重复，但仍要求保留实质信息。
   - **正式专业**：适合正式报告，避免空泛或夸大的措辞。
4. 选择强度：轻度调整、平衡改写、深入改写。强度越高不代表检测分数一定越低。
5. 选择生成方式：一个候选，或默认的三个候选。每个候选都以原文为基础，不是对上一版反复改写。
6. 按需填写“保留术语”，用逗号分隔，例如 `Java RMI, BHEL, API`。
7. 可选填一段自己写的英文，最多 3,000 字符，用于参考语气和用词；模型可能无法完全遵循。
8. 点击“开始润色”。

### 候选生成和检查

三个策略分别为“清楚直接”“重组句式”“保留作者语气”。每个候选先检查：

- 指定术语是否遗漏。
- 数字、引用和直接引语是否被改动。
- 篇幅是否变化过大。
- 是否新增某些不可见控制字符或可疑异形字。

字面检查通过后，再调用同一个本地模型做一次独立语义复核。复核失败、不可用或发现问题的候选不会自动推荐。复核是辅助检查，不保证内容完全正确。

### 如何选择版本

- 点击“原文”或不同候选按钮查看文本和检查说明。
- 原文和候选统一用 Nuts **规则模型**做参考比较，不混用不同引擎。
- 原文可评分时，自动选择通过检查且规则评分更低的候选；没有这样的候选就保留原文。
- 少于 80 词时不比较检测分数，仅按自动检查结果选择。
- 重复生成的版本会显示“重复”。

展开“查看修改对比”可以查看新增和删除的文字。使用前核对事实、限定条件、数字和引用；尤其要留意否定和因果关系。

### 等待和停止

每个候选可能包含两次模型请求，每次最长等待 5 分钟。三个候选在最慢情况下可能接近 30 分钟，并非保证几秒完成。

“当前候选完成后停止”只阻止后续候选，不会强行中断已经发给 Ollama 的请求。已完成的结果会保留。

## 7. 记录四个平台的实测成绩

当前程序没有自动连接 Turnitin、GPTZero、ZeroGPT 或 QuillBot，也没有这些平台的已验证成绩。

1. 在 Nuts 选中一个候选，复制完整文本。
2. 在你有权限使用的平台测试相同文本。保持各平台测试文本一致，避免只测局部后填为整篇结果。
3. 回到 Nuts，展开“记录外部检测实测 · 目标 0%”。
4. 分别填入原文和当前候选的分数。仅在平台确实给出数值时填写 0–100；未测试、无法访问或结果不可用时留空。
5. 切换候选后，填写该候选自己的结果；原文成绩共用。
6. 保存本轮实验 JSON。

这里的 0% 是实验目标，不是保证。各平台分数定义可能不同；人工录入的分数不会被 Nuts 自动核验。即使四项都录入 0，也只代表这个版本的一次记录，不能推断其他文章同样有效。

为了判断改进是否有效，建议保留每轮原文、候选、设置和实际成绩。不要只记录表现最好的一篇；记录没有改善或变差的结果同样有用。

## 8. 保存结果和实验数据

- **复制结果**：复制当前查看版本的纯文本。
- **下载 TXT**：保存当前查看版本为 `nuts-polished.txt`。
- **用作原文**：把当前版本放回左侧输入框。
- **撤销替换**：恢复上一次替换前的原文。
- **导出本轮实验 JSON**：包括原文、所有候选、模型和设置、检查结果、手工成绩及录入时间。

Nuts 不自动保存输入和结果。刷新页面或关闭标签页会丢失当前实验；需要时先导出。第二版暂未提供 JSON 导入恢复界面，可以用文本编辑器查看导出内容。

建议把个人文章和实验记录放在项目的 `private/` 中，或放到仓库之外。不要把包含私人文本的实验 JSON 提交到公开 GitHub。

## 9. macOS 和 Linux

安装 Python 后，在项目目录运行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

macOS 环境准备好后，可以双击 `start.command`。若脚本没有执行权限：

```sh
chmod +x start.command
./start.command
```

润色仍需另外安装 Ollama、下载模型并保持服务运行。Linux 的 Ollama 服务启动方式请按 [官方说明](https://docs.ollama.com/linux) 操作。

## 10. 更新项目和换电脑

### 用 Git 下载的项目

先保存实验并关闭正在运行的 Nuts。在项目文件夹执行：

```powershell
git status --short
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.bat
```

如果有自己改过的文件，先备份或提交；`git pull` 报冲突时不要直接删除自己的修改。`--ff-only` 失败意味着本地与远程已分叉，需要先处理分支差异。

### 用 ZIP 下载的项目

重新下载 GitHub ZIP，解压到新文件夹，按安装步骤运行。旧目录保留到新版本确认可用为止。Ollama 已下载的模型通常可继续使用，不需要因为项目换目录而重新下载。

### 换电脑

复制源码和需要保留的私人文件即可。不要复制原电脑的 `.venv`，尤其不要把 Mac 环境复制给 Windows；模型缓存也不包含在 GitHub 仓库里。目标电脑需要重新准备 Python 环境和本地模型。

## 11. 故障排查

| 问题 | 怎么处理 |
|---|---|
| `py` 不存在或找不到 3.12 | 安装 Python 3.12 和 Launcher，重新打开终端，检查 `py -3.12 --version`。 |
| 双击 `start.bat` 提示先安装 | 先运行 `setup.bat`；确认目录下有 `.venv\Scripts\python.exe`。 |
| pip 下载失败 | 检查网络，保留报错信息；恢复网络后重新运行 `setup.bat`。 |
| 浏览器打不开 | 确认服务终端没有退出，使用终端打印的实际端口；不要直接打开 `analyzer.html`。 |
| GPT-2 不可用，只剩规则 | 确认依赖已安装，检查首次模型下载网络，重新检测。 |
| Ollama 未连接 | 启动 Ollama，执行 `ollama list`；页面点“刷新连接”。 |
| Ollama 已连接但没有模型 | 执行 `ollama pull qwen2.5:7b`，完成后刷新。 |
| 生成很慢、超时或内存不足 | 先选一个候选、缩短原文、关闭其他大程序；必要时换小模型。 |
| 显示“模型正在处理其他请求” | 等待已有任务完成，不要在多个标签页同时发模型任务。 |
| 语义复核未完成 | 可能超时、返回格式无效或模型不支持所需输出；本次不会自动推荐，可换模型再试。 |
| 全部候选都不推荐 | 检查具体原因；保留原文是正常兜底行为，不表示程序坏了。 |
| 数字/引用只是改了格式也被标记 | 字面检查较保守，重新核对原文与结果；不要自动忽略。 |
| 刷新后记录消失 | 当前版本不自动保存，之后在刷新前先导出 JSON。 |
| `git pull` 提示会覆盖修改 | 先备份或提交自己的文件，再处理更新，不要强行重置。 |

### 可选 GPU 加速

`setup.bat` 使用普通依赖安装，不保证所装 PyTorch 是合适的 CUDA 构建。需要 NVIDIA 加速时，查看 [PyTorch 官方安装器](https://pytorch.org/get-started/locally/)，按电脑驱动和系统选择安装命令，使用项目内 Python 的 `-m pip` 执行。

PyTorch 和 Ollama 是两个独立的运行环境；Ollama GPU 正常并不代表 Python 的 CUDA 可用。不要因为速度慢直接假定必须重新训练模型。

## 12. 开发、测试和提交 GitHub

### 自动检查

Windows：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m py_compile server.py rewriting.py rewrite_quality.py
node --check app.js
git diff --check
```

macOS / Linux：

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m py_compile server.py rewriting.py rewrite_quality.py
node --check app.js
git diff --check
```

没有 Node 时，Python/JS 一致性测试会跳过；要完整验证请安装 Node。GPT-2 测试需要检测依赖和已下载或能下载的模型。润色集成测试使用模拟本地 Ollama，不会下载润色模型，也不证明实际生成质量。

### 修改后提交

仅对自己有写入权限的仓库操作：

```sh
git status --short
git diff
```

检查内容后，用 `git add 文件名` 选择需要提交的源码和说明，再执行：

```sh
git commit -m "Describe the change"
git push origin main
```

不确定时先开开发分支，例如 `git switch -c codex/my-change`，推送该分支并通过 Pull Request 合并。不要用强制推送覆盖远程历史。

### 研究用途：重新训练与评测

仅想运行网站不需要此步骤。要重新训练检测器时，另外安装评测依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-eval.txt
.\.venv\Scripts\python.exe evaluate.py fetch
.\.venv\Scripts\python.exe evaluate.py run --no-bino
```

这会下载评测数据，并重写 `model.json` 和评测报告。耗时、资源需求明显高于日常使用。不要把重新训练与润色功能混为一件事。

## 13. 文件导航与当前限制

| 文件 | 用途 |
|---|---|
| [README.md](README.md) | 项目入口、文档导航和检测研究说明 |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | 较短的本地安装说明 |
| [analyzer.html](analyzer.html)、[app.css](app.css)、[app.js](app.js) | 页面、样式、候选和实验记录交互 |
| [server.py](server.py) | 本地 HTTP 服务、输入检查和模型任务控制 |
| [rewriting.py](rewriting.py) | Ollama 生成、策略、语义复核 |
| [rewrite_quality.py](rewrite_quality.py) | 字面保留检查与统一规则评分 |
| [nuts-core.js](nuts-core.js)、[textfeatures.py](textfeatures.py)、[model.py](model.py) | 检测计算逻辑 |
| [model.json](model.json) | 已训练的评分参数和评测数据，不是大语言模型权重 |
| [perplexity.py](perplexity.py) | GPT-2 指标计算 |
| [tests/](tests/) | 自动测试 |
| [reports/evaluation.md](reports/evaluation.md) | 既有检测引擎评测 |
| [reports/local-v2-validation.md](reports/local-v2-validation.md) | 第二版验证证据和未验证部分 |
| [PLAN.md](PLAN.md) | 旧检测升级计划，未实施部分仍是后续计划 |

当前不提供：账号、云端历史记录、在线付费、DOCX/PDF 导入、外部检测器自动提交、语义正确性的保证或全平台 0% 保证。

第二版已有功能测试和模拟服务的页面验证；实际 Windows 环境、真实 Ollama 润色质量与速度、四个平台的检测效果仍需在目标电脑实测。
