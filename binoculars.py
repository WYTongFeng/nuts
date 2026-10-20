"""Binoculars 指标（Hans et al., ICML 2024）：用两个相近的语言模型互相对照，判断文字是否由 AI 生成。

单看困惑度时，专业名词、专有名词多的文字天然难猜，会被当成人写的。Binoculars 把
执行模型的困惑度除以两个模型之间的交叉困惑度：后者衡量这段文字的题材本来就有多难猜，
相除之后题材的影响大致抵消。分数越低越像 AI。

观察模型 Qwen2.5-0.5B，执行模型 Qwen2.5-0.5B-Instruct，两者共用一个分词器。
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

OBSERVER = "Qwen/Qwen2.5-0.5B"
PERFORMER = "Qwen/Qwen2.5-0.5B-Instruct"
MAX_LEN = 512   # 词表有 15 万个词，窗口小一点省内存
STRIDE = 256
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
DTYPE = torch.float32 if DEVICE == "cpu" else torch.float16

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()
_models = None


def downloaded():
    return all(isinstance(try_to_load_from_cache(m, "config.json"), str) for m in (OBSERVER, PERFORMER))


def load():
    global _models
    if _models is None:
        if not downloaded():
            print("首次运行，正在下载 Binoculars 用的两个 Qwen 模型（约 2GB）…", file=sys.stderr)
        tok = AutoTokenizer.from_pretrained(PERFORMER)
        observer = AutoModelForCausalLM.from_pretrained(OBSERVER, dtype=DTYPE).to(DEVICE).eval()
        performer = AutoModelForCausalLM.from_pretrained(PERFORMER, dtype=DTYPE).to(DEVICE).eval()
        _models = (tok, observer, performer)
    return _models


def token_scores(text):
    """每个 token 返回 (字符起点, 字符终点, 执行模型的负对数概率, 两个模型的交叉熵)。"""
    tok, observer, performer = load()
    enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
    # 开头补 <|endoftext|>，让第一个词也能被打分
    ids = [tok.convert_tokens_to_ids("<|endoftext|>")] + enc["input_ids"]
    offsets = [(0, 0)] + enc["offset_mapping"]

    scores = []
    pos = 1
    while pos < len(ids):
        end = min(pos + STRIDE, len(ids))
        begin = max(0, end - MAX_LEN)
        window = torch.tensor([ids[begin:end]], device=DEVICE)
        rows = slice(pos - begin - 1, end - begin - 1)  # logits[j] 是对窗口内第 j+1 个 token 的预测
        with torch.no_grad():
            log_p = torch.log_softmax(performer(window).logits[0, rows].float(), dim=-1)
            q = torch.softmax(observer(window).logits[0, rows].float(), dim=-1)
            targets = torch.tensor(ids[pos:end], device=DEVICE).unsqueeze(1)
            nll = -log_p.gather(1, targets).squeeze(1)
            xent = -(q * log_p).sum(dim=-1)
        scores += [(s, e, n, x) for (s, e), n, x in zip(offsets[pos:end], nll.tolist(), xent.tolist())]
        pos = end
    return scores


def details(text):
    """返回 (整体指标, 逐句指标)，逐句指标和 textfeatures.sentence_spans() 一一对应。"""
    norm = textfeatures.normalize(text)
    core = norm.strip()
    if not core:
        return {}, []
    lead = len(norm) - len(norm.lstrip())
    scores = token_scores(core)

    spans = textfeatures.sentence_spans(norm)
    groups = [[] for _ in spans]
    owners = textfeatures.sentence_of_tokens(spans, lead, [(s, e) for s, e, _, _ in scores])
    for i, (_, _, n, x) in zip(owners, scores):
        if i is not None:
            groups[i].append((n, x))

    def ratio(pairs):
        return statistics.mean(n for n, _ in pairs) / statistics.mean(x for _, x in pairs)

    overall = {
        "bino": ratio([(n, x) for _, _, n, x in scores]),
        "qwen_ppl": math.exp(statistics.mean(n for _, _, n, _ in scores)),
    }
    sentences = [{"bino": ratio(g), "tokens": len(g)} if g else None for g in groups]
    return overall, sentences
