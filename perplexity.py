"""语言模型指标：用 GPT-2 给每个 token 打分，复现 GPTZero 一类检测器的核心原理。

- ppl（困惑度）：模型对这段文字有多意外。AI 生成的文字每个词都很好猜，困惑度偏低
- sent_ppl_std（句困惑度波动）：各句困惑度的标准差。人写的忽高忽低，AI 写的比较平
- top10（Top-10 占比）：有多少词落在模型预测的前 10 名里（GLTR 方法），AI 文本通常更高
"""
import logging
import math
import statistics
import sys

# torch 在 macOS 上导入时会打印一条无关警告，先屏蔽
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)

import torch
from huggingface_hub import try_to_load_from_cache
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.utils import logging as hf_logging

import textfeatures

MODEL_NAME = "gpt2"
MAX_LEN = 1024  # GPT-2 的上下文上限
STRIDE = 512    # 长文本按滑动窗口打分，每个 token 至少带 512 个 token 的上文
MIN_SENTENCE_TOKENS = 3  # 计算句困惑度波动时，跳过太短的句子
# 有 NVIDIA 显卡就用；Mac 上留在 CPU（GPT-2 很小，CPU 够快，结果也和已有缓存一致）
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()
_model = None
_tokenizer = None


def load():
    global _model, _tokenizer
    if _model is None:
        if not isinstance(try_to_load_from_cache(MODEL_NAME, "config.json"), str):
            print("首次运行，正在下载 GPT-2 模型（约 500MB）…", file=sys.stderr)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME).to(DEVICE).eval()
    return _model, _tokenizer


def token_scores(text):
    """每个 token 返回 (字符起点, 字符终点, 负对数概率, 在模型预测中的排名)。"""
    model, tok = load()
    enc = tok(text, return_offsets_mapping=True)
    # 开头补 <|endoftext|>，让第一个词也有东西可以预测它
    ids = [tok.bos_token_id] + enc["input_ids"]
    offsets = [(0, 0)] + enc["offset_mapping"]

    scores = []
    pos = 1
    while pos < len(ids):
        end = min(pos + STRIDE, len(ids))
        begin = max(0, end - MAX_LEN)
        with torch.no_grad():
            logits = model(torch.tensor([ids[begin:end]], device=DEVICE)).logits[0]
        # logits[j] 是对窗口内第 j+1 个 token 的预测
        rows = logits[pos - begin - 1 : end - begin - 1]
        target_logits = rows.gather(1, torch.tensor(ids[pos:end], device=DEVICE).unsqueeze(1))
        nll = torch.logsumexp(rows, dim=1) - target_logits.squeeze(1)
        ranks = (rows > target_logits).sum(dim=1) + 1
        scores += [(s, e, n, r) for (s, e), n, r in zip(offsets[pos:end], nll.tolist(), ranks.tolist())]
        pos = end
    return scores


def details(text):
    """返回 (整体指标, 逐句指标)。

    逐句指标和 textfeatures.sentence_spans() 切出来的句子一一对应（网页的切句也一样），
    句子里没有 token 时是 None。
    """
    norm = textfeatures.normalize(text)
    core = norm.strip()  # 首尾空白不参与打分，文件末尾多一个换行不该改变结果
    if not core:
        return {}, []
    lead = len(norm) - len(norm.lstrip())
    scores = token_scores(core)

    spans = textfeatures.sentence_spans(norm)
    groups = [[] for _ in spans]
    owners = textfeatures.sentence_of_tokens(spans, lead, [(s, e) for s, e, _, _ in scores])
    for i, (_, _, n, r) in zip(owners, scores):
        if i is not None:
            groups[i].append((n, r))

    sent_ppl = [math.exp(statistics.mean(n for n, _ in g)) for g in groups if len(g) >= MIN_SENTENCE_TOKENS]
    overall = {
        "ppl": math.exp(statistics.mean(n for _, _, n, _ in scores)),
        "sent_ppl_std": statistics.pstdev(sent_ppl) if len(sent_ppl) > 1 else None,
        "top10": sum(r <= 10 for _, _, _, r in scores) / len(scores),
    }
    sentences = [
        {
            "ppl": math.exp(statistics.mean(n for n, _ in g)),
            "top10": sum(r <= 10 for _, r in g) / len(g),
            "tokens": len(g),
        } if g else None
        for g in groups
    ]
    return overall, sentences


def score(text):
    return details(text)[0]
