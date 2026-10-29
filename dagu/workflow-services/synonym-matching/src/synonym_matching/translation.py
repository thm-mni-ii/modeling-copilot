"""Local German-to-English translation, once per distinct nonempty text."""
import time
from importlib.metadata import version


class Translator:
    def __init__(self, config, cache):
        self.config = config
        self.cache = cache
        self.model = None
        self.load_seconds = 0.0
        self.compute_seconds = 0.0
        self.revision = None

    def _load(self):
        if self.model is not None:
            return
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        started = time.perf_counter()
        name = self.config.get("translation_model", "Helsinki-NLP/opus-mt-de-en")
        revision = self.config.get("translation_revision", "main")
        self.tokenizer = AutoTokenizer.from_pretrained(name, revision=revision)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(name, revision=revision).eval()
        self.revision = getattr(self.model.config, "_commit_hash", None) or revision
        self.load_seconds = time.perf_counter() - started

    def translate(self, texts, languages):
        if any(text.strip() and lang not in {"de", "en"} for text, lang in zip(texts, languages)):
            raise ValueError("translation requires explicit de/en language for each nonempty label")
        german = list(dict.fromkeys(t for t, lang in zip(texts, languages) if lang == "de" and t.strip()))
        translated = {}
        if german:
            self._load()
            namespace = {"kind": "translation-v1", "model": self.config.get("translation_model", "Helsinki-NLP/opus-mt-de-en"),
                         "revision": self.revision, "source": "de", "target": "en", "beams": 1,
                         "transformers": version("transformers"), "torch": version("torch")}
            translated = dict(zip(german, self.cache.get_many(namespace, german, self._compute), strict=True))
        return [translated[t] if lang == "de" and t.strip() else t for t, lang in zip(texts, languages)]

    def _compute(self, texts):
        import torch
        started = time.perf_counter()
        result = []
        batch_size = self.config.get("batch_size", 32)
        for offset in range(0, len(texts), batch_size):
            batch = self.tokenizer(texts[offset:offset + batch_size], return_tensors="pt", padding=True,
                                   truncation=False)
            if batch["input_ids"].shape[1] > 512:
                raise ValueError("translation input exceeds 512 tokens; shorten labels explicitly")
            with torch.inference_mode():
                output = self.model.generate(**batch, do_sample=False, num_beams=1, max_new_tokens=256)
            result.extend(self.tokenizer.batch_decode(output, skip_special_tokens=True))
        self.compute_seconds += time.perf_counter() - started
        return result
