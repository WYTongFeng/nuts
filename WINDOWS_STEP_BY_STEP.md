# Nuts：Windows 从零安装与运行教程

适用：已经从 GitHub 下载 Nuts，准备在另一台 Windows 电脑本地运行。

日期：2026-10-23。请按顺序完成；每一步都有“成功标志”。本文命令都在 **PowerShell** 输入，一次复制一条，按 Enter 执行，不要复制代码框外的说明。

## 先了解需要安装的三样东西

| 项目 | 负责什么 | 是否需要安装 |
|---|---|---|
| Python 3.12 | 运行 Nuts 网站和英文检测 | 需要 |
| Ollama | 在本机运行英文润色模型 | 使用润色时需要 |
| Qwen3 4B、Gemma3 4B、Qwen2.5 7B | 多模型润色与统一复核 | 在 Ollama 里下载，可先只装一个 |

不需要购买 API Key，不需要先安装 Node.js、VS Code 或 Git。第一次安装和下载模型需要网络。

本教程按普通 Intel / AMD 64 位 Windows 电脑编写。Ollama 官方要求 Windows 10 22H2 或更新版本；Windows 11 也适用。[官方系统要求](https://docs.ollama.com/windows)

建议先预留约 20GB 可用空间作为安装和缓存余量；这是本教程的准备建议，不是精确的运行最低要求。首次跑通时给笔记本接上电源，并关闭不必要的大型程序。

## 第 1 步：把下载的 ZIP 完整解压

如果还没下载：

1. 打开 [Nuts GitHub 仓库](https://github.com/WYTongFeng/nuts)。
2. 点击绿色 **Code**。
3. 点击 **Download ZIP**。

下载后：

1. 打开“下载”文件夹。
2. 右键 ZIP，选择“全部提取 / Extract All”。
3. 把解压出来的项目文件夹放在你容易找到的位置，例如“文档”里。
4. 打开文件夹，直到你能直接看到以下文件：

   ```text
   setup.bat
   start.bat
   server.py
   analyzer.html
   model.json
   requirements.txt
   ```

文件夹可能叫 `nuts-main` 或 `Nuts-local-v2`，名字不影响运行。

**成功标志：你是在普通文件夹里看到上述文件，不是在 ZIP 压缩包里面。**

不要双击 `analyzer.html` 启动网站；后面要使用 `start.bat`。

## 第 2 步：打开 PowerShell，先检查 Python

1. 按键盘 Windows 键。
2. 输入 `PowerShell`。
3. 打开 **Windows PowerShell**，普通模式即可。
4. 输入：

   ```powershell
   py -3.12 --version
   ```

如果显示 `Python 3.12.x`，表示已安装，可以直接跳到第 4 步。

如果提示找不到 `py` 或没有 Python 3.12，继续第 3 步。

## 第 3 步：安装 Python 3.12

本项目的 `setup.bat` 会寻找 Python 3.12，所以只装另一个版本并不一定能直接使用脚本。

### 3.1 安装 Python Install Manager

1. 打开 [Python 官方下载页面](https://www.python.org/downloads/)。
2. 下载 Windows 的 **Python Install Manager**，按安装程序提示完成安装。
3. 关闭之前打开的 PowerShell。
4. 重新打开一个 PowerShell 窗口。

Python 官方目前提供安装管理器来安装指定版本。不要选择 embeddable package（嵌入式压缩包）代替正常开发环境。[Python Windows 官方说明](https://docs.python.org/3/using/windows.html)

### 3.2 安装 3.12 运行环境

输入：

```powershell
py install 3.12
```

等待下载、安装完成后输入：

```powershell
py -3.12 --version
```

**成功标志：显示 `Python 3.12.x`，最后的小版本号可以不同。**

### 如果 `py install 3.12` 报“找不到 install 文件”

这通常说明电脑上的 `py` 仍然是旧版 Python Launcher。确认你已安装新的 Python Install Manager，然后改用：

```powershell
pymanager install 3.12
```

之后再次运行：

```powershell
py -3.12 --version
```

如果 `py` 仍然不能找到新安装的 3.12，但下面命令能显示版本：

```powershell
pymanager -3.12 --version
```

在第 4 步打开项目目录的 PowerShell 后，先手动建立环境：

```powershell
pymanager -3.12 -m venv .venv
```

再执行 `setup.bat`。它会复用已经建立的 `.venv`，不需要调用旧 `py` 建环境。

如果两个命令都找不到，请重新打开终端；仍不行时检查安装管理器是否安装完成。不要连续执行后面的步骤掩盖这个问题。

## 第 4 步：安装 Nuts 的 Python 依赖

### 4.1 从项目文件夹打开 PowerShell

1. 回到第 1 步解压的项目文件夹。
2. 确认此处能看到 `setup.bat` 和 `server.py`。
3. 点击文件资源管理器上方的地址栏。
4. 输入 `powershell`，按 Enter。
5. 在打开的 PowerShell 输入：

   ```powershell
   dir setup.bat
   ```

**成功标志：命令列出 `setup.bat` 文件，而不是提示找不到。**

以后本文说“项目目录的 PowerShell”，就是这个窗口。

### 4.2 运行安装脚本

输入：

```powershell
.\setup.bat
```

等待安装完成。脚本会建立 `.venv` 文件夹，并安装 PyTorch、Transformers 等检测依赖。

安装时间取决于网络，看到下载进度时让它继续，不要反复开多个安装窗口。

**成功标志：最后出现 `Setup complete`，并提示可以运行 `start.bat`。**

按任意键结束安装脚本，然后可以验证依赖：

```powershell
.\.venv\Scripts\python.exe -c "import torch, transformers; print('Python dependencies OK')"
```

显示 `Python dependencies OK` 就可以继续。

如果安装失败，先看本文后面的故障排查。不要把 Mac 电脑的 `.venv` 拷过来代替安装。

## 第 5 步：安装 Ollama

1. 打开 [Ollama Windows 下载页面](https://ollama.com/download/windows)。
2. 下载官方安装程序。
3. 双击并按提示安装。
4. 从 Windows 开始菜单打开 **Ollama**。
5. 如果出现模型或登录选择，选择本地模型流程。本项目不需要云模型登录或 API Key。
6. 关闭旧的 PowerShell 窗口，再新开一个。
7. 输入：

   ```powershell
   ollama --version
   ```

**成功标志：显示 Ollama 的版本信息。**

Windows 版 Ollama 安装后可以在后台运行，并提供本机接口。Nuts 会连接它的 `127.0.0.1:11434`。[Ollama Windows 官方说明](https://docs.ollama.com/windows)

如果只是找不到 `ollama` 命令，先重新打开 PowerShell；还不行再检查是否安装成功，不需要重复下载模型。

## 第 6 步：下载润色模型

RTX 3060 Laptop 6GB 显存建议先装下面三个，逐行执行、等上一行完成后再执行下一行：

```powershell
ollama pull qwen3:4b
ollama pull gemma3:4b
ollama pull qwen2.5:7b
```

前两个用于生成不同候选，第三个用于统一复核。可以先只装 Qwen3 4B，使用单候选模式；无需一次下载全部 9 个模型。其他模型和完整下载清单见 [模型指南](MODEL_GUIDE.md)。

下面以原有 Qwen2.5 7B 为例检查安装；已下载则跳过重复下载：

这一步的命令可以在任意文件夹的 PowerShell 里执行，不一定要在 Nuts 项目目录。

输入：

```powershell
ollama pull qwen2.5:7b
```

等待进度完成。这是模型文件下载，不是安装 Python 包。

[qwen2.5:7b 官方模型页面](https://ollama.com/library/qwen2.5:7b)标注模型文件约 **4.7GB**；运行时还需要额外内存。不要因为文件大小小于显存就认为一定能完全装进显卡。

下载完成后输入：

```powershell
ollama list
```

**成功标志：列表中出现 `qwen2.5:7b`。**

如果网络中断，可以重新运行同一条 `ollama pull qwen2.5:7b` 命令重试。

## 第 7 步：先测试 Ollama 模型能否工作

在 PowerShell 输入：

```powershell
ollama run qwen2.5:7b "Rewrite this sentence clearly without changing its meaning: The system allows users to check their booking status. Return only the rewritten sentence."
```

第一次加载模型可能需要等一会儿。

**成功标志：终端输出一段英文回答，而不是连接失败或内存不足。** 具体措辞不必和任何示例相同。

如果进入 `>>>` 聊天提示符，可以输入 `/bye` 退出聊天。退出聊天后 Ollama 后台服务仍可继续运行。

为了让测试后模型退出内存，可执行：

```powershell
ollama stop qwen2.5:7b
```

这不会删除已下载的模型；网站下一次需要时会再加载。[Ollama 命令参考](https://docs.ollama.com/cli)

### 如果 7B 模型太慢或内存不够

先下载较小的版本试跑：

```powershell
ollama pull qwen2.5:1.5b
```

再测试：

```powershell
ollama run qwen2.5:1.5b "Rewrite clearly: The system allows users to check their booking status."
```

之后在 Nuts 里选择 `qwen2.5:1.5b`。小模型可以用于先确认流程，但不能据此保证润色质量和检测效果。

## 第 8 步：启动 Nuts 网站

1. 确保 Ollama 仍在后台运行。
2. 回到 Nuts 项目文件夹。
3. 双击 `start.bat`。

也可以在项目目录的 PowerShell 输入：

```powershell
.\start.bat
```

**成功标志：终端出现类似下面的提示，浏览器自动打开中文网站。**

```text
Nuts 已启动：http://localhost:8000（Ctrl+C 停止）
```

如果浏览器没有自动打开，把终端显示的完整地址复制到 Edge 或 Chrome 地址栏。

8000 被占用时程序会尝试 8001–8010，所以始终以终端显示的地址为准。

**不要关闭这个终端窗口。** 它正在运行网站，关闭之后页面就连接不上服务了。

## 第 9 步：第一次使用英文润色

先用一个候选和短文本确认功能，成功后再使用三个候选处理长文。

1. 在网站选择“英文润色”。
2. 点击“刷新连接”。
3. 在“润色模型 1”中选择 `qwen2.5:7b`；如果你下载的是小模型，就选择对应的名字。
4. 首次设置建议如下：

   | 设置 | 首次测试的选择 |
   |---|---|
   | 润色风格 | 自然流畅 |
   | 改写强度 | 平衡改写 |
   | 生成方式 | 1 个候选 + 语义复核 |
   | 统一复核模型 | 使用润色模型 1 |
   | 运行配置 | RTX 3060 · 自适应 4K / 8K |
   | 保留术语 | 可先留空 |
   | 你的英文写作样本 | 可先留空 |

5. 在原文框粘贴：

   ```text
   The booking system allows students to check available rooms before submitting a request. Staff can review each request and update its status. This reduces the need to ask for updates by email. However, students still need to provide accurate information when making a booking.
   ```

6. 点击“开始润色”。
7. 等待生成和语义复核完成。
8. 点击候选版本查看结果、检查提示和修改对比。

**成功标志：出现候选版本或明确的检查结果，而不是“未连接 Ollama”。**

这段短示例少于 80 词，所以本地检测参考会显示“不评分”，这是正常行为，不影响生成润色候选。

如果结果保留原文，先阅读原因：候选可能未通过内容检查或语义复核，或者没有达到选择条件。生成出候选但未自动推荐，不等于安装失败。

### 第 9A 步：开启自动多模型润色与复核

1. 确认 `ollama list` 中有 `qwen3:4b`、`gemma3:4b` 和 `qwen2.5:7b`。
2. 在网站点击“刷新连接”。
3. 按下表选择：

   | 设置 | 推荐值 |
   |---|---|
   | 生成方式 | 多模型各生成 1 个 + 统一复核 |
   | 润色模型 1 | qwen3:4b |
   | 润色模型 2（多模型模式） | gemma3:4b |
   | 润色模型 3（多模型模式） | 不使用；需要更多对照时再选 |
   | 统一复核模型 | qwen2.5:7b |
   | 运行配置 | RTX 3060 · 自适应 4K / 8K |

4. 先粘贴一段较短英文，点击“开始润色”。
5. 页面先显示每个模型的生成进度，再显示统一复核进度。所有模型分别读取同一份原文。
6. 完成后点击“版本 1”“版本 2”，核对生成模型、复核模型和各自耗时。
7. 检查事实、数字、引用和原意。复核未完成或发现问题的候选不会自动推荐，但仍可以查看。
8. 如需提前结束，点击“当前请求结束后停止”。当前调用会继续至完成或超时，后续生成和复核停止；未复核版本不会自动推荐。
9. 展开“记录外部检测实测”，填入真实测试结果并导出实验 JSON。导出包含模型配置、每个候选、复核及耗时；刷新网页前先保存。

**成功标志：两个不同模型的候选都出现，并显示指定的统一复核模型。** 如果只出现一个，检查另一个是否选择了“不使用”、重复选中了相同模型，或生成失败。重复的模型选择会自动合并。

“3 个候选 + 语义复核”仍表示润色模型 1 使用三种编辑策略；模型 2、3 只在多模型模式生效。“使用润色模型 1”表示所有候选统一交给模型 1 复核，不是分别交回各自生成模型。

模型按顺序运行，不会同时运行三个。两生成模型 + 一个复核模型，通常是两次生成、两次复核。每次推理请求最长等待 5 分钟，另有加载、释放等开销；这不是实际速度承诺。

### 第 9B 步：RTX 3060 速度与显存设置

- 默认配置按请求大小选择 4K 或 8K 上下文，并限制输出长度。不是所有文章都会使用 4K。
- 同一批次内保留模型，换模型前释放上一个；整轮完成或正常停止后释放模型。异常关闭网页时模型通常在保温期（5 分钟）后释放。
- 对支持关闭思考的模型，程序请求关闭思考；并非所有模型都允许。
- 若之前用过 GPT-2 检测，润色前会将 GPT-2 移回系统内存，减少显存争用。
- 若 7B 复核很慢，把“统一复核模型”换为 `qwen3:4b` 或 `phi4-mini`（后者需先下载）；速度与质量都需实测。
- 提示超过上下文预算时，缩短原文或写作样本。2,000 词是输入上限，不保证所有 2,000 词文本都能放进 8K 上下文。
- 不要同时开游戏、其他本地大模型聊天任务或多个 Nuts 润色任务。程序只管理自己加载的 Ollama 模型，不会清理其他应用的模型。

可在任务运行时另开 PowerShell 执行 `ollama ps` 查看 GPU/CPU 分配。短文也显示 CPU/GPU 混合时，先换 3B–4B 模型再比较速度。

### 已安装旧版的 Windows 用户如何更新

1. 导出并保存当前结果；在运行网站的终端按 `Ctrl+C` 停止旧服务。
2. 在 GitHub 下载最新 ZIP，解压到新文件夹，避免覆盖自己保存的文本和实验记录。不要把 Mac 的 `.venv` 复制到 Windows。
3. 在新文件夹运行 `setup.bat`，成功后运行 `start.bat`。Ollama 模型保存在独立位置，无需因为换项目文件夹重新下载。
4. 如果原来使用 Git 克隆且没有自己的代码改动，可在项目文件夹执行 `git pull --ff-only`，然后重新运行 `setup.bat` 和 `start.bat`；若提示有冲突，不要强制覆盖，改用新文件夹安装。
5. 浏览器按 `Ctrl+F5` 刷新。看到“润色模型 2”“统一复核模型”“运行配置”即说明新界面已加载。

## 第 10 步：第一次使用英文检测

1. 切换到“英文检测”。
2. 点击“试试示例”，或者输入至少 80 个英文词。
3. 点击“检测文本”。
4. 等待 GPT-2 首次下载和加载；第一次需要联网。
5. 查看右侧分数、判断依据和逐句结果。

**成功标志：结果区域显示 `GPT-2 + 规则`。**

如果显示 `仅规则 · 降级模式`，说明页面能工作，但 GPT-2 尚未成功运行。检查 Python 依赖和网络后重试。

这里的 GPT-2 和 Ollama 润色模型是两套独立模型：

- `ollama list` 不会显示 GPT-2。
- 润色可用不代表 GPT-2 已下载好。
- 检测可用也不代表已经安装润色模型。

## 第 11 步：以后每天怎样使用

首次安装成功以后，不需要每天重复运行安装脚本或重新下载模型。

每次使用：

1. 开机后确认 Ollama 在运行；不确定时从开始菜单打开它。
2. 打开 Nuts 文件夹。
3. 双击 `start.bat`。
4. 在浏览器使用检测或润色。
5. 需要保留的结果点击“下载 TXT”或“导出本轮实验 JSON”。
6. 用完后在运行 Nuts 的终端按 `Ctrl+C`，再关闭终端。

刷新网页或关闭页面前先保存结果。当前版本不自动保存原文、候选和实验记录。

## 第 12 步：常见问题，按对应情况处理

### A. PowerShell 找不到 `setup.bat` 或 `start.bat`

你可能不在项目目录，或漏写了前面的 `.\`。

回到能看到 `server.py` 的文件夹，在地址栏输入 `powershell`，然后运行：

```powershell
.\setup.bat
```

### B. 安装脚本报错或窗口很快关掉

从项目目录的 PowerShell 手动执行，便于保留报错：

```powershell
py -3.12 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

前一条失败时先解决它，不要继续下一条。已有有效 `.venv` 时只需重试安装依赖。

不需要运行 `Activate.ps1`，也不需要修改 PowerShell 的执行策略。

### C. Ollama 未连接

先从开始菜单打开 Ollama，然后在 PowerShell 输入：

```powershell
ollama list
```

- 能列出模型：回到 Nuts 点击“刷新连接”。
- 报连接失败：Ollama 后台服务没有正常启动。

只有确认后台没运行时，才可尝试：

```powershell
ollama serve
```

此时保留这个窗口，再开另一个窗口运行 Nuts。如果提示 `11434` 地址已被占用，说明该端口已有服务，不要重复启动多个 `ollama serve`；回到原 Ollama 应用检查状态。

### D. Ollama 连接正常，但下拉框没有模型

执行：

```powershell
ollama list
```

如果没有需要的模型，就执行：

```powershell
ollama pull qwen2.5:7b
```

等待完成后刷新。安装 Ollama 应用本身，不代表已经下载模型。

### E. 模型太慢或内存不足

按顺序尝试：

1. 生成方式改成一个候选。
2. 先用几十到几百词，确认短文能完成。
3. 关闭游戏和其他大模型程序。
4. 润色和复核都先选择 `qwen3:4b`；仍不够再试备用的 `qwen2.5:1.5b`。
5. 若有 NVIDIA 显卡，检查官方驱动是否正常安装。

模型正在运行时，可以另开 PowerShell 输入：

```powershell
ollama ps
```

`PROCESSOR` 列可帮助判断使用 CPU、GPU 还是混合运行；不是 GPU 并不代表程序完全不能用。[Ollama 官方说明](https://docs.ollama.com/faq#how-can-i-tell-if-my-model-was-loaded-onto-the-gpu)

Nuts 在切换模型和整轮任务结束时会要求卸载模型；同一模型连续复核时保持加载。因此任务结束后 `ollama ps` 为空也可能是正常的。

### F. 网站开了，但不能检测

在项目目录检查：

```powershell
.\.venv\Scripts\python.exe -c "import torch, transformers; print('Python dependencies OK')"
```

若报缺包，重新运行 `setup.bat`。如果依赖正常但首次下载失败，检查网络后重新检测。

### G. 已有结果变灰

输入或设置改变了，当前显示的是旧结果。重新点击处理按钮即可。

### H. 为什么本地分数低，其他网站仍可能高？

Nuts 不是这些平台的同一套检测器，分数不能互换。当前没有四个平台的已验证效果；正常安装也不意味着达到全平台 0%。

## 可选设置：让 Ollama 只使用本地功能

1. Windows 搜索“编辑账户的环境变量”。
2. 在用户变量中点击“新建”。
3. 变量名填 `OLLAMA_NO_CLOUD`。
4. 变量值填 `1`。
5. 保存后完全退出 Ollama，再从开始菜单重新打开。

这不会删除本地模型。[Ollama 官方本地模式说明](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)

## 安装完成检查表

- [ ] ZIP 已解压，项目目录中能直接看到 `server.py`。
- [ ] `py -3.12 --version` 能显示版本，或已按管理器替代步骤创建环境。
- [ ] `setup.bat` 安装成功，依赖检查输出 `Python dependencies OK`。
- [ ] `ollama --version` 能显示版本。
- [ ] `ollama list` 能看到所选模型。
- [ ] 模型的命令行测试能返回英文。
- [ ] `start.bat` 能打开中文网站。
- [ ] 润色页能连接本地模型并生成候选。
- [ ] 检测页能显示结果，并看清使用的是完整模型还是规则模式。

教程根据当前项目脚本和官方文档整理；目标 Windows 电脑尚未现场验证。更多更新、实测记录及开发步骤见 [完整操作手册](OPERATIONS.md)。
