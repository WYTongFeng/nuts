# Nuts 升级计划（在 Lenovo 上执行）

> 2026-10-23 更新：用户已将第一版范围扩展为“中文界面、英文检测与润色、本地运行”。当前使用说明见 [LOCAL_SETUP.md](LOCAL_SETUP.md)。下文是之前的检测升级计划，其中“只做检测”的旧范围不再适用于当前版本；更强检测模型、训练和速度目标仍未完成。

这份文档写给接手的人：用户本人，或者在 Lenovo 上运行的 Claude。照着它做，不需要看之前的聊天记录。每一步都写了要做什么、怎么做、做到什么程度算完成。

## 1. 目标和约束

用户的要求，按优先级：

1. **准确率尽量高。**
2. **完全免费**：不用付费 API，不用付费服务。开源模型、免费数据集、本地计算都可以。
3. **尽量快**：检测一篇报告要在几秒内出结果。
4. **界面像商业检测器**：左边原文直接高亮，右边是仪表盘、结论和原因（详见第 6 步）。用户对现在的界面不满意。

另外两条一直要遵守：

- 所有准确率数字都必须在检测模型**没见过**的数据上测出来，写进 `reports/evaluation.md`。不能只拿一两段文字调参，也不能拿训练数据来报成绩。
- 用户用中文交流，界面和报告都用中文。

## 2. 范围

Nuts 是检测和分析工具：判断文字像不像 AI 写的，解释原因，公开准确率。**不做改写文字、降低 AI 分数或绕过检测器的功能。**

## 3. 硬件

Lenovo IdeaPad Gaming 3 16IAH7，Windows：

- CPU：第 12 代 Intel 酷睿 i5（标压）
- GPU：NVIDIA GeForce RTX 3060 Laptop，**通常是 6GB 显存**（用 `nvidia-smi` 确认）
- 内存：24GB（16 + 8）
- 硬盘：512GB SSD，需要预留约 25GB 给模型、数据和缓存

显存预算：同时加载的所有模型，合计不超过约 5GB（半精度）。

另一台 MacBook（M2，8GB 内存）跑不动大模型，只用来看网页、做不需要 GPU 的开发。

## 4. 现状（2026-10-20）

### 文件

| 文件 | 作用 |
|---|---|
| `textfeatures.py` | 文本清理、切句、分段、规则指标。`nuts-core.js` 是它的 JS 逐行对照版 |
| `perplexity.py` | GPT-2 困惑度、Top-10 占比、逐句分数（有 CUDA 就用 GPU） |
| `binoculars.py` | Binoculars 分数，用 Qwen2.5-0.5B 和 Qwen2.5-0.5B-Instruct。**代码写好了，还没评测完** |
| `model.py`、`model.json` | 逻辑回归综合模型、阈值、各指标的人写 / AI 中位数（`feature_stats`）、评测结果（`evaluation`） |
| `evaluate.py` | `fetch` 下载评测数据，`run` 训练和评测，生成 `model.json` 和报告 |
| `server.py` | 本地网页服务器：`/` 页面，`/nuts-core.js`、`/model.json` 静态文件，`POST /api/score` 语言模型打分 |
| `analyzer.html` | 网页（A / B 两段对比的旧界面，要按第 6 步重做） |
| `analyzer.py` | 命令行 |
| `tests/` | 26 个测试：切句、清理、MATTR、GPT-2 对齐、服务器、Python / JS 一致性（需要 node） |

`model.json` 里有三种引擎的位置：`bino`（Binoculars + GPT-2 + 规则）、`full`（GPT-2 + 规则）、`rules`（只用规则）。`model.engine()` 和 `nuts-core.js` 的 `engine()` 按拿到的分数自动选最好的一种。现在的 `model.json` 只训练了 `full` 和 `rules`。

### 已经测出的准确率

数据：RAID（ACL 2024）的论文摘要、书籍概要、新闻，人写 450 篇；GPT-4、ChatGPT、Llama-2-chat、Mistral-chat、Cohere-chat、MPT-chat 各 75 篇。按原文章分组划分训练集和测试集。另有 2026 基准 700 篇，只用来测试。

| 引擎 | AUROC | “很可能”线：误判 / 检出 | “可能”线：误判 / 检出 |
|---|---|---|---|
| GPT-2 + 规则 | 0.963 | 2.4% / 79.5% | 12.0% / 89.7% |
| 仅规则 | 0.885 | 4.8% / 48.7% | 12.0% / 69.2% |

2026 基准（“可能”线，GPT-2 + 规则）：2026 年模型检出 98%；非母语作者论文段落误判 21%；2022 年前维基百科误判 19%；公版文学误判 0.7%。完整数字见 `reports/evaluation.md`。

### 已知问题（这次升级要解决的）

1. **术语多的技术文本会被判成人写。** 用户截图里有一段约 80 词的 HRM 系统报告（Java RMI、BHEL、salted password hashing 这类词很多）：GPT-2 版判 5%、不标任何句子；仅规则版判 87%；某商业检测器判 100% AI。原因是专业名词让 GPT-2 的困惑度变高。原文**不要**放进仓库，需要时请用户贴出来，放在 `private/`（已在 `.gitignore` 里）。
2. **非母语作者误判率 21%。**
3. **训练数据里没有学生作业**，也没有技术报告。
4. **仅规则版对 2026 年模型只认出 38%–75%。**
5. **界面**：用户要的是单篇检测器的样式（第 6 步），不是现在的 A / B 对比。

## 5. 总体方案

不从零训练。把几个已经训练好的开源检测模型组合起来，在它们没见过的数据上测试和校准；只有测出明显短板时，才自己微调。

```
文本 ──┬─ 现成检测模型（desklib、vanguard、rasbt……）── 各自的 AI 概率
       ├─ Binoculars（两个 Qwen 模型）───────────── 零样本分数
       ├─ GPT-2 困惑度、Top-10 占比 ────────────── 辅助特征
       └─ 规则指标（突发性、套话……）───────────── 辅助特征
                         │
                 逻辑回归组合 + 按误判率定阈值
                         │
          整篇判断 + 逐句高亮 + 原因（对比人写 / AI 中位数）
```

对组合没有帮助的模型最后都要删掉，换取速度。

## 6. 步骤

### 第 0 步：在 Lenovo 上准备环境

1. 安装：Git、Python 3.12（安装时勾选 “Add python.exe to PATH”）、最新的 NVIDIA 驱动、Node.js LTS（用于一致性测试）。
2. 克隆仓库，进入文件夹。
3. 建虚拟环境：`py -3.12 -m venv .venv`
4. 安装 PyTorch：先运行 `nvidia-smi` 看右上角的 CUDA Version，然后到 https://pytorch.org/get-started/locally/ 选 Windows / Pip / Python / 不高于这个版本的 CUDA，复制命令，把开头的 `pip` 换成 `.venv\Scripts\python -m pip`。
5. 安装其余依赖：`.venv\Scripts\python -m pip install -r requirements.txt -r requirements-eval.txt`
6. 验证 GPU：`.venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"`，应该输出 `True` 和 `NVIDIA GeForce RTX 3060 Laptop GPU`。
7. 跑现有测试：`.venv\Scripts\python -m unittest discover -s tests`
8. 重新下载评测数据（`data/` 没放进 Git）：`.venv\Scripts\python evaluate.py fetch`

Windows 注意事项：
- 文档里的 `.venv/bin/python` 在 Windows 上一律换成 `.venv\Scripts\python`。直接用这个路径，不用激活虚拟环境，可以避开 PowerShell 的执行策略问题。
- Hugging Face 的模型缓存在 `%USERPROFILE%\.cache\huggingface`。

**完成标准**：CUDA 可用；现有测试全部通过；`data/raid.jsonl` 和 `data/bench2026.jsonl` 下载完成。

### 第 1 步：评测数据

| 数据集 | 用途 | 许可 | 注意 |
|---|---|---|---|
| RAID（`liamdugan/raid`） | 已有 900 篇 | MIT | desklib 用 RAID 训练过，它在 RAID 上的分数会虚高，不能用来训练组合模型 |
| `textsightai/ai-text-detection-benchmark-2026` | **只测试** | CC BY-SA 4.0 | 有 2026 年模型、非母语作者论文段落、维基、文学 |
| `rasbt/human-vs-ai-50k` | 只用它的 `test` 划分（5066 条） | 每条有自己的许可 | 有技术博客，最接近技术报告；rasbt 模型用它的 train 训练过 |
| `SJTU-CL/ArguGPT` | 非母语学生作文 + AI 作文 | 先确认具体许可 | 专门测非母语误判 |
| PERSUADE 2.0 + DAIGT | 学生作文 + AI 作文 | 先确认来源和许可 | 选可信的镜像 |
| 本地新生成的 AI 文本 | 组合模型的训练和校准 | 自己生成 | 见下 |
| 用户 2022 年以前自己写的作业 | 人写技术报告，只测误判 | 用户自己的 | 放 `private/`，不上传 |

**本地新生成 AI 文本**（推荐，免费但要几个小时）：用 Ollama（Windows 安装最简单）在 3060 上跑 7B 到 9B 的开源模型的 4-bit 版本，比如 `qwen2.5:7b`、`llama3.1:8b`、`mistral:7b`、`gemma2:9b`。按人写文本的题目和长度生成对应的 AI 版本，再加一批技术报告类题目（系统设计报告、实验报告、文献综述）。这些文本任何检测模型都没见过，是最干净的校准数据。预计每个模型每秒 30 到 40 个 token，1000 篇约 2 到 3 小时。

划分规则：
- 同一题目或来源的人写和 AI 文本放在同一组（`GroupKFold`）。
- **只测试**的集合不参与任何训练、阈值选择或特征选择。
- 每个检测模型训练过哪些数据，要在报告里写清楚，对应的成绩标成“可能虚高”。

**完成标准**：`evaluate.py fetch` 能下载以上数据（许可不允许或拿不到的，在报告里写明原因并跳过）；每条数据都有 `group`、`label`、`dataset`、`domain`、`model` 字段。

### 第 2 步：给现成的检测模型逐个打分

| 模型 | 底座 | 许可 | 权重大小 | 训练数据 | 加载方式 |
|---|---|---|---|---|---|
| `desklib/ai-text-detector-v1.01` | DeBERTa-v3-large | MIT | 1.7GB | RAID | 自定义类 `DesklibAIDetectionModel`，见下 |
| `desklib/ai-text-detector-academic-v1.01` | DeBERTa-v3-large | MIT | 1.7GB | 学术写作（看模型卡） | 同上 |
| `ShantanuT01/vanguard-ai-text-detector` | ModernBERT-large | MIT | 1.6GB | 模型卡未写，先查 | `ModernBertForSequenceClassification` |
| `rasbt/ai-text-detector-modernbert` | ModernBERT-base | Apache-2.0 | 0.3GB | `rasbt/human-vs-ai-50k` | `ModernBertForSequenceClassification` |
| `fakespot-ai/roberta-base-ai-text-detection-v1` | RoBERTa-base | Apache-2.0 | 0.5GB | 模型卡未写，先查 | `RobertaForSequenceClassification` |

实现要点：
- 新建 `detectors.py`，统一接口：`score(texts) -> [AI 概率]`，以及逐句打分（第 5 步）。半精度、批量推理，在 GPU 上运行。
- **desklib**：仓库里只有权重，没有代码。按它的模型卡（README）里给出的类定义自己实现（DeBERTa 编码器 + 平均池化 + 一个线性层 + sigmoid），用 safetensors 以 `strict=True` 加载权重，确认每个权重都对上了，再用模型卡的示例核对输出。
- **不要使用 `trust_remote_code=True`**，不要运行模型仓库里的 `.py` 文件。
- 标签方向看 `config.id2label`，再用一段明显的 AI 文本和一段明显的人写文本核对。
- 长文本按 512 token 切块，按每块的 token 数加权平均。
- 分数缓存到 `data/<模型名>_cache.jsonl`，可以直接复用 `evaluate.score_cache()`。
- 顺便把 Binoculars 也跑完：先用现在的 0.5B 那一对；显存允许的话再试 Qwen2.5-1.5B 那一对（8-bit 量化）。

**完成标准**：每个模型在每个评测集上的 AUROC、误判率 1% 和 5% 时的检出率、非母语误判率，都写进 `reports/evaluation.md`。

### 第 3 步：组合与校准

- 输入：各检测模型的 logit、Binoculars、GPT-2 特征、规则特征。
- 模型：逻辑回归（和现在的 `fit_with_thresholds()` 一样，用交叉验证的预测来定阈值）。
- 阈值：“很可能是 AI”按误判率 1% 到 2% 定，“可能有 AI 成分”按 5% 到 10% 定。
- 训练数据：只用检测模型没见过的数据（本地新生成的数据，加上 rasbt test 的一半等）。
- 报告分项：整体、按 AI 模型、按领域、非母语误判、技术文本误判、按长度（50 / 100 / 200 / 400+ 词）、RAID 里被改写攻击过的文本（paraphrase、synonym 等，测稳健性）。
- 逐个去掉模型看效果，只保留真正有贡献的，换取速度。
- 更新 `model.py`、`nuts-core.js` 的特征列表和 `engine()`、`server.py` 的返回内容、`analyzer.py`，保持 Python / JS 一致性测试通过。

**完成标准**：新的 `model.json` 和 `reports/evaluation.md`；报告里有新旧引擎的对比。

### 第 4 步：按需微调（只在第 3 步测出明显短板时做）

- 底座：ModernBERT-base（或 DeBERTa-v3-base），半精度，`max_length` 512，batch 8 到 16，训练 2 到 3 轮。3060 上预计 30 到 90 分钟。
- 数据：RAID（包括 paraphrase 等攻击版本）、rasbt train、ArguGPT 和 DAIGT 的训练部分、本地新生成的数据。
- 用同一套测试集评测，只有确实更好才加进组合。

### 第 5 步：逐句打分

- 每句连同前后各一句一起交给检测模型打分。
- 逐句阈值单独校准：人写句子被标“很像 AI”不超过约 5%，被标“有点像”不超过约 15%。
- 每句的原因：检测模型的分数，加上套话、句长等规则特征。

### 第 6 步：新界面（照用户截图）

用户截图里的商业检测器长这样，Nuts 按这个结构做（用 Nuts 自己的名字和配色，不照抄别人的品牌）：

- **主卡片，左右两栏**
  - **左边，输入框**：检测后，句子直接在原文里高亮，红色深浅表示程度，AI 套话加波浪下划线。右上角有清空按钮。底部有字数统计、导入 .txt 按钮、“检测”按钮（快捷键 Ctrl / Cmd + Enter）。
  - **右边，结果**：
    1. 半圆仪表盘，绿、黄、红渐变，中间大字显示 AI 可能性的百分比。
    2. 结论框：图标加一句话，分为“很可能是 AI 生成”“可能有 AI 成分”“不太像 AI 生成”“文本太短，不下结论”“不是英文”。
    3. “在原文中高亮”开关。
    4. “判断依据”列表：每条前面一个红点（指向 AI）或绿点（指向人写）。写出这段文字的数值，并和人写、AI 的中位数对比（来自 `model.json` 的 `feature_stats`），比如“平均每词 5.9 个字母（人写中位数 4.9，AI 中位数 5.1）”。按每个特征对判断的贡献排序。
    5. “最像 AI 的句子”前 5 句，点一下就在输入框里选中那句。
- 检测后再修改文本：高亮隐藏，结果变灰，提示“文本改过了，点检测更新结果”。
- 在输入框里点某一句：右边显示这句的分数和原因。
- 下方：
  - 详细指标表：这段文字、人写中位数、AI 中位数、区分力。
  - 准确率：来自 `model.json` 的 `evaluation`。
  - 指标说明和局限。
- 技术做法：`textarea` 下面叠一层字体、内边距、换行完全相同的高亮层（文字透明，只显示背景色），滚动同步；用 `ResizeObserver` 保持两层宽度一致。
- 两种运行方式：
  - **本地完整版**：`server.py` 提供页面和 `/api/score`。
  - **claude.ai 链接版**：只有浏览器能力，不能调用外部服务，也不能下载模型。只用规则（加上第 7 步的统计模型，如果启用的话），页面上要写清楚准确率较低。
- 手机宽度（400px）也能用，有深色模式，不能出现横向滚动。

### 第 7 步：浏览器统计模型（给链接版用，可选）

- 词 1 到 3 gram 的逻辑回归，只保留权重绝对值最大的 2 万到 5 万个特征，导出成 JSON（小于 3MB）。JS 里实现同样的分词和打分，加进一致性测试。
- 只有在测试集上明显好于现有规则时才启用。

### 第 8 步：速度

- 1000 词的报告，整篇加逐句，在 3060 上不超过 2 秒。
- `server.py` 启动时预加载所有模型，打印每个模型的显存占用。
- 没有 GPU 时（比如 Mac）自动退回 CPU，只加载最小的组合：可以慢一点，但要能用。

### 第 9 步：收尾

- 测试：现有测试，加上检测模型的加载和输出测试（没有 GPU 时跳过）、服务器接口测试、Python / JS 一致性测试。
- `start.bat`：双击就用 `.venv\Scripts\python server.py` 启动。
- 更新 README：Windows 和 macOS 两套命令、新的准确率表、局限。
- 更新 claude.ai 链接版：需要在登录了 claude.ai 的 Claude 会话里重新发布 `analyzer.html`，连同 `nuts-core.js` 和 `model.json` 一起。原链接：https://claude.ai/artifact/SnzDdBfbWkFfrtFUNf7ib6

## 7. 验收标准

- `reports/evaluation.md` 里有每个检测模型和组合模型的数字，包括非母语误判率和技术文本误判率，并标明哪些成绩可能因训练数据重叠而虚高。
- 在只用于测试的数据上，组合模型比现在的 GPT-2 + 规则更好：AUROC 更高、低误判率下的检出率更高。非母语误判率目标在 10% 以下（“可能”线）。达不到的话，在报告里写清楚差在哪里。
- 用户那段 HRM 报告，记录每个引擎的结果作为个案。但不能拿它来调参。
- 页面符合第 6 步。
- 所有测试通过。

## 8. 注意事项

- 安全：不用 `trust_remote_code`，只加载 safetensors 权重，不运行下载下来的脚本。
- 隐私：用户的作业和测试文本放在 `private/`，不提交到 Git。
- 许可：模型都是 MIT 或 Apache-2.0。数据集各有许可，`data/` 不提交到 Git。用到新数据集之前先确认许可，并写进 README 的“数据来源”。
- 显存：用半精度，不用的模型及时释放；如果显存不够，优先删掉对组合贡献最小的模型。
- 一个很现实的上限：自己做的检测器，不会和 Turnitin、GPTZero 的结论完全一致。最能提升准确率的，是收集几百份接近真实用途的文本（学生技术报告的人写版和 AI 版）。
