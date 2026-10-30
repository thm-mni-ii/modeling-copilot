"""Übersetzt deutsche Labels ins Englische und verwendet Ergebnisse wieder."""

from importlib.metadata import version


class Translator:
    """Verwaltet das lokale Übersetzungsmodell und einen gemeinsamen Cache."""

    def __init__(self, config, cache):
        """Merke Einstellungen; Modellgewichte werden erst bei Bedarf geladen."""
        self.config = config
        self.cache = cache
        self.model = None
        self.revision = None

    def _load(self):
        """Lade Modell und Tokenizer genau einmal pro Instanz."""
        if self.model is not None:
            return
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        name = self.config.get('translation_model', 'Helsinki-NLP/opus-mt-de-en')
        revision = self.config.get('translation_revision', 'main')
        self.tokenizer = AutoTokenizer.from_pretrained(name, revision=revision)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            name, revision=revision
        ).eval()
        self.revision = getattr(self.model.config, '_commit_hash', None) or revision

    def translate(self, texts, languages):
        """Übersetze nur deutsche Texte; behalte Englisch und leere Texte bei."""
        german_texts = []
        for text, language in zip(texts, languages):
            if text.strip() and language not in {'de', 'en'}:
                raise ValueError(
                    'translation requires explicit de/en language '
                    'for each nonempty label'
                )
            if language == 'de' and text.strip() and text not in german_texts:
                german_texts.append(text)

        translations = {}
        if german_texts:
            self._load()
            # Eine andere Modellrevision darf keine alten Cachewerte verwenden.
            namespace = {
                'kind': 'translation-v1',
                'model': self.config.get(
                    'translation_model', 'Helsinki-NLP/opus-mt-de-en'
                ),
                'revision': self.revision,
                'source': 'de',
                'target': 'en',
                'beams': 1,
                'transformers': version('transformers'),
                'torch': version('torch'),
            }
            translated_texts = self.cache.get_many(
                namespace, german_texts, self._compute
            )
            translations = dict(zip(german_texts, translated_texts, strict=True))

        result = []
        for text, language in zip(texts, languages):
            if language == 'de' and text.strip():
                result.append(translations[text])
            else:
                result.append(text)
        return result

    def _compute(self, texts):
        """Übersetze unbekannte Labels stapelweise, ohne zufälliges Sampling."""
        import torch

        result = []
        batch_size = self.config.get('batch_size', 32)
        for offset in range(0, len(texts), batch_size):
            batch_texts = texts[offset:offset + batch_size]
            batch = self.tokenizer(
                batch_texts, return_tensors='pt', padding=True, truncation=False
            )
            # Zu lange Labels nicht still abschneiden: Das verändert die Bedeutung.
            if batch['input_ids'].shape[1] > 512:
                raise ValueError(
                    'translation input exceeds 512 tokens; shorten labels explicitly'
                )
            with torch.inference_mode():
                output = self.model.generate(
                    **batch, do_sample=False, num_beams=1, max_new_tokens=256
                )
            result.extend(
                self.tokenizer.batch_decode(output, skip_special_tokens=True)
            )
        return result
