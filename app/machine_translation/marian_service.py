import logging
from transformers import MarianMTModel, MarianTokenizer

logger = logging.getLogger(__name__)

class MarianMTService:
    def __init__(self):
        self.models = {}
        self.tokenizers = {}
        
        self.supported_pairs = {
            ("en", "fr"), ("fr", "en"),
            ("en", "es"), ("es", "en"),
            ("en", "ar"), ("ar", "en"),
            ("en", "zh"), ("zh", "en"),
        }

    def _get_model_name(self, src: str, tgt: str) -> str:
        return f"Helsinki-NLP/opus-mt-{src}-{tgt}"

    def preload_models(self):
        logger.info("Preloading all MarianMT models (this may take a while)...")
        for src, tgt in self.supported_pairs:
            self._load_model(src, tgt, self._get_model_name(src, tgt))
        logger.info("Finished preloading models.")

    def _load_model(self, src: str, tgt: str, model_name: str):
        pair = (src, tgt)
        if pair not in self.models:
            logger.info(f"Loading model {model_name} for {src}-{tgt}...")
            self.tokenizers[pair] = MarianTokenizer.from_pretrained(model_name)
            self.models[pair] = MarianMTModel.from_pretrained(model_name)
            logger.info(f"Model {model_name} loaded successfully.")

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:

        pair = (source_lang, target_lang)
        if pair not in self.supported_pairs:
            raise ValueError(f"Language pair {source_lang}-{target_lang} is not supported.")
            
        model_name = self._get_model_name(source_lang, target_lang)
        
        if pair not in self.models:
            self._load_model(source_lang, target_lang, model_name)
            
        tokenizer = self.tokenizers[pair]
        model = self.models[pair]

        translated_tokens = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        
        return translated_text
