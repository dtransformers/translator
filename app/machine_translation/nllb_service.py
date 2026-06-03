import logging
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

logger = logging.getLogger(__name__)

class NLLBService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        
        # Mapping from ISO 639-1 / standard API codes to FLORES-200 codes
        self.lang_mapping = {
            "en": "eng_Latn",
            "fr": "fra_Latn",
            "es": "spa_Latn",
            "ar": "arb_Arab",
            "zh": "zho_Hans",
        }
        
        self.model_name = "facebook/nllb-200-3.3B"

    def preload_models(self):
        logger.info(f"Preloading NLLB model {self.model_name} (this may take a while)...")
        self._load_model()
        logger.info("Finished preloading NLLB model.")

    def _load_model(self):
        if self.model is None or self.tokenizer is None:
            logger.info(f"Loading tokenizer and model for {self.model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            logger.info(f"Model {self.model_name} loaded successfully.")

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        if source_lang not in self.lang_mapping:
            raise ValueError(f"Source language '{source_lang}' is not supported.")
        if target_lang not in self.lang_mapping:
            raise ValueError(f"Target language '{target_lang}' is not supported.")
            
        src_lang_flores = self.lang_mapping[source_lang]
        tgt_lang_flores = self.lang_mapping[target_lang]
        
        if self.model is None or self.tokenizer is None:
            self._load_model()
            
        tokenizer = self.tokenizer
        model = self.model
        if tokenizer is None or model is None:
            raise RuntimeError("NLLB model or tokenizer failed to load.")
            
        # Set the source language for the tokenizer
        tokenizer.src_lang = src_lang_flores

        inputs = tokenizer(text, return_tensors="pt", padding=True)
        translated_tokens = model.generate(
            **inputs, 
            forced_bos_token_id=tokenizer.lang_code_to_id[tgt_lang_flores]
        )
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        
        return translated_text
