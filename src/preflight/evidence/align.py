import re
import statistics
from collections.abc import Callable
from functools import cache

Span = tuple[float, float]
# (mono s16 PCM, sample rate, words) -> seconds from the PCM's start per word (None if unalignable), score 0-1
Aligner = Callable[[bytes, int, list[str]], tuple[list[Span | None], float]]


def letters(word: str) -> str:
    # "53p" read as "p" would pin the word to the p and cut "fifty-three" out of its segment
    return "" if re.search(r"\d", word) else re.sub(r"[^a-z']", "", word.lower())


@cache
def load():
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    return bundle.get_model().eval(), bundle.get_dict(), bundle.sample_rate


def mms_aligner() -> Aligner | None:
    try:
        import torch
        import torchaudio.functional as F
    except ImportError:
        return None

    def align(pcm: bytes, rate: int, words: list[str]) -> tuple[list[Span | None], float]:
        model, labels, model_rate = load()
        spelt = [letters(w) for w in words]
        if not any(spelt):
            return [None] * len(words), 0.0
        wave = torch.frombuffer(bytearray(pcm), dtype=torch.int16).float().div(32768).unsqueeze(0)
        if rate != model_rate:
            wave = F.resample(wave, rate, model_rate)
        with torch.inference_mode():
            emission = torch.log_softmax(model(wave)[0], dim=-1)
            targets = torch.tensor([[labels[c] for w in spelt for c in w]], dtype=torch.int32)
            path, scores = F.forced_align(emission, targets, blank=0)
        tokens = F.merge_tokens(path[0], scores[0].exp())
        seconds = wave.shape[1] / model_rate / emission.shape[1]
        spans: list[Span | None] = []
        first = 0
        for w in spelt:
            if not w:
                spans.append(None)
                continue
            mine = tokens[first:first + len(w)]
            first += len(w)
            spans.append((mine[0].start * seconds, mine[-1].end * seconds))
        # median over letters of each letter's mean frame probability; the mean is dragged down by slurred letters
        return spans, statistics.median(t.score for t in tokens)

    return align
