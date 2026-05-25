from typing import Optional

def build_translation_context(
    source_lang: str,
    target_lang: str,
    glossary: Optional[dict[str, str]] = None,
    translation_memory: Optional[list[dict[str, str]]] = None
) -> str:
    """
    Builds a string context injecting domain knowledge, glossaries, 
    and translation memory examples.
    """
    context_parts = []
    
    if glossary and len(glossary) > 0:
        context_parts.append("### Glossary:")
        for term, translation in glossary.items():
            context_parts.append(f"- '{term}' -> '{translation}'")
            
    if translation_memory and len(translation_memory) > 0:
        context_parts.append("\n### Translation Memory Examples:")
        for example in translation_memory:
            src = example.get("source", "")
            tgt = example.get("target", "")
            if src and tgt:
                context_parts.append(f"Source: {src}\nTarget: {tgt}\n")
                
    if not context_parts:
        return "No specific context provided. Translate normally."
        
    return "\n".join(context_parts)
