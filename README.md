# Nuts

> **本地第二版已加入多候选英文润色。** 中文工作台、英文检测、本地 Ollama 多候选润色、保留检查与外部实测记录。另一台电脑的安装启动步骤见 [LOCAL_SETUP.md](LOCAL_SETUP.md)：Windows 先运行 `setup.bat`，再运行 `start.bat`。润色需单独安装 Ollama 并下载模型。下方保留原检测引擎的研究说明与评测；既有评测数字不代表润色效果。

## 先从这里开始

**Windows 新手请先看：[从零安装与运行教程](WINDOWS_STEP_BY_STEP.md)**。每一步都列出操作、命令与成功标志，包含 Python、Ollama 和模型安装。

**完整操作手册：[OPERATIONS.md](OPERATIONS.md)**，包含 GitHub 下载、Windows / macOS 安装、Ollama、检测、三候选润色、实测记录、保存、更新与故障排查。

| 想做什么 | 看哪里 |
|---|---|
| 第一次在另一台电脑使用 | [完整操作手册](OPERATIONS.md) / [简版安装说明](LOCAL_SETUP.md) |
| 查看第二版测试结果和限制 | [第二版验证记录](reports/local-v2-validation.md) |
| 查看检测引擎历史评测 | [检测评测报告](reports/evaluation.md) |
| 了解后续检测升级设想 | [旧计划](PLAN.md) |

Windows 快速开始：从本仓库 **Code → Download ZIP** 下载并解压，安装 Python 3.12，运行 `setup.bat`，再运行 `start.bat`。润色需单独安装 Ollama 并执行 `ollama pull qwen2.5:7b`。网站运行在本机，GitHub 只存源码和文档。

当前润色支持多候选、改写强度、自己的写作样本、内容检查和手工外部成绩记录。**尚无四个平台的已验证成绩，也不保证全平台 0%。** 下方数字属于既有检测模型，不是改写效果。

## 检测引擎背景

英文文本的 AI 特征分析器，用来研究 AI 检测：判断一段文字像不像 AI 写的，解释原因，逐句标出最像 AI 的地方，并公开自己的准确率。

Nuts 不是 Turnitin 或 GPTZero，两边的结果不能互换。任何检测器都会误判，非英语母语作者的文字尤其容易被误判。

**原检测升级计划见 [PLAN.md](PLAN.md)**：更强检测模型等未实施内容仍是后续计划；当前中文工作台已更新。

## 开发者安装（检测与重新评测）

日常使用请优先按上方操作手册执行，无需安装评测依赖。

需要 Python 3.10 以上（Windows 推荐 3.12）。

1. 建虚拟环境：

   ```bash
   python -m venv .venv
   ```

2. 安装 PyTorch：
   - **Windows + NVIDIA 显卡**：到 https://pytorch.org/get-started/locally/ 选 Windows / Pip / Python / CUDA（版本参考 `nvidia-smi` 显示的 CUDA Version），复制那条命令，把开头的 `pip` 换成 `.venv\Scripts\python -m pip` 运行。
   - **macOS**：`.venv/bin/python -m pip install torch`

3. 安装其余依赖（Windows 把 `.venv/bin/python` 换成 `.venv\Scripts\python`，下同）：

   ```bash
   .venv/bin/python -m pip install -r requirements.txt -r requirements-eval.txt
   ```

第一次运行会下载 GPT-2 模型（约 500MB），之后从本地缓存加载。

## 使用

1. **旧检测版网页链接**（不含本次新增润色）：https://claude.ai/artifact/SnzDdBfbWkFfrtFUNf7ib6 。只有规则指标，准确率比完整版低。链接默认是私有的，要给别人看需要在页面的 Share 菜单里分享。
2. **本地网页**（完整版，含 GPT-2）：

   ```bash
   .venv/bin/python server.py
   ```

   会自动在浏览器打开。8000 端口被占用时会自动换下一个端口。
3. **命令行**：

   ```bash
   .venv/bin/python analyzer.py 文件.txt
   .venv/bin/python analyzer.py 文件1.txt 文件2.txt     # 并排对比
   .venv/bin/python analyzer.py --sentences 文件.txt     # 列出最像 AI 的句子
   .venv/bin/python analyzer.py --no-lm 文件.txt         # 不用 GPT-2
   ```

## 准确率

完整数据在 [reports/evaluation.md](reports/evaluation.md)，用 `evaluate.py` 可以重新跑出来。

训练和测试用的是 RAID 数据集（ACL 2024）里的论文摘要、书籍概要和新闻：人写文本，以及 GPT-4、ChatGPT、Llama-2-chat、Mistral-chat、Cohere-chat、MPT-chat 按同样标题生成的文本。测试集按原始文章分组划开，同一标题的人写和 AI 文本不会同时出现在训练集和测试集里。

| 版本 | AUROC | “很可能是 AI”：误判 / 检出 | “可能有 AI 成分”：误判 / 检出 |
|---|---|---|---|
| GPT-2 + 规则（本地版） | 0.963 | 2.4% / 79.5% | 12.0% / 89.7% |
| 仅规则（网页链接版） | 0.885 | 4.8% / 48.7% | 12.0% / 69.2% |

“误判”指人写文本被判成 AI，“检出”指 AI 文本被认出来。

另外用一个完全没参与训练的 2026 年基准做了测试（GPT-2 + 规则，“可能有 AI 成分”这条线）：

- 2026 年模型（Claude Opus 5、Claude Haiku 4.5、GPT-4.1、gpt-oss、Qwen）写的文本：检出 98%
- **非英语母语作者写的论文段落：误判 21%**
- 2022 年以前的维基百科：误判 19%
- 公版文学作品：误判 0.7%

逐句检查：会把 4.6% 的人写句子标成“很像 AI”，AI 句子是 40%。

## 指标

| 指标 | 含义 | 区分力（AUROC） |
|---|---|---|
| 困惑度 | GPT-2 读这段文字有多意外，越低越像 AI | 0.875 |
| 段落长度 CV | 各段长短的变化，越低越像 AI（只算两段以上的文章，容易受排版影响，不参与判断） | 0.867 |
| Top-10 占比 | 有多少词落在 GPT-2 预测的前 10 名里，越高越像 AI | 0.866 |
| 突发性（句长 CV） | 句子长短的变化程度，越低越像 AI | 0.817 |
| AI 套话 / 千词 | AI 文本明显更常用的短语出现的频率 | 0.809 |
| 句困惑度波动 | 各句困惑度的标准差，越低越像 AI | 0.751 |
| 平均词长 | 词的平均字母数，越高越像 AI | 0.641 |
| 逗号 / 句 | 每句的逗号数 | 0.574 |
| 词汇多样性（MATTR） | 每 50 个词里不重复的比例 | 0.505 |
| 平均句长 | 每句的词数 | 0.502 |

综合判断是一个逻辑回归模型。GPT-2 版的输入是困惑度、Top-10 占比、句困惑度波动、突发性、AI 套话、平均词长、逗号 / 句；仅规则版去掉前三项。

套话表一部分从训练数据统计出来（只保留在三个领域里都偏向 AI 的短语），一部分来自旧版手写的套话里数据没有反驳的那些。furthermore、moreover、leverage、seamless、holistic、not only 在数据里人写文本用得一样多甚至更多，已经删掉。

## 局限

- 训练数据只有论文摘要、书籍概要和新闻，没有学生作文。
- 训练用的 AI 文本来自 2023 年的模型。
- 专业名词多的技术文本会被 GPT-2 版偏判成人写（困惑度被术语抬高）。
- 非母语作者的正式文字、维基百科这类格式固定的文体，误判率明显更高。
- 写得口语化的 AI 文字识别不出来。`samples/casual.txt` 其实也是 AI 写的（故意写成口语），Nuts 判它不到 1%。
- 只支持英文；少于 80 个词时不下结论。

## 重新评测

```bash
.venv/bin/python evaluate.py fetch            # 下载评测数据到 data/（只需一次）
.venv/bin/python evaluate.py run              # 训练、评测，写出 model.json 和 reports/evaluation.md
.venv/bin/python evaluate.py run --no-bino    # 跳过 Binoculars（没有显卡时很慢）
```

语言模型的分数缓存在 `data/` 里，中断后可以接着跑。`data/` 不上传到 Git。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests
```

`tests/test_consistency.py` 用 node 跑 `nuts-core.js`，确认网页和 Python 算出的特征、概率完全一致；没装 node 时会跳过。

## 文件

| 文件 | 作用 |
|---|---|
| `analyzer.html`、`app.css`、`app.js` | 中文检测与润色工作台 |
| `nuts-core.js` | 规则和评分计算，与 Python 保持一致 |
| `rewriting.py` | 本地 Ollama 润色接口 |
| `LOCAL_SETUP.md`、`setup.bat`、`start.bat` | 另一台电脑的安装和启动 |
| `server.py` | 本地网页服务器，提供语言模型打分接口 |
| `analyzer.py` | 命令行 |
| `textfeatures.py` | 文本清理、切句、分段和规则指标 |
| `perplexity.py` | GPT-2 困惑度、Top-10 占比，以及逐句分数 |
| `binoculars.py` | Binoculars 分数（两个 Qwen2.5-0.5B 模型，已写好，还没评测完） |
| `model.py`、`model.json` | 综合模型、阈值、各指标的人写 / AI 中位数和评测结果 |
| `evaluate.py` | 下载数据、训练、评测 |
| `reports/evaluation.md` | 评测报告 |
| `PLAN.md` | 下一步的升级计划 |
| `samples/` | 两段演示文字，都是 Claude 写的 |
| `tests/` | 自动测试 |

## 数据来源

- RAID：Dugan et al., *RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors*, ACL 2024，MIT 许可。
- textsightai/ai-text-detection-benchmark-2026，CC BY-SA 4.0。

`data/` 里的数据只用于本地评测，使用时请遵守各自的许可。
