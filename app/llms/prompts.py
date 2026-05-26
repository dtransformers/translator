import json
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

def get_summary_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a content analyst.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Summarize the file for translation context.

Constraints:
- Output language: {target_language}
- One short paragraph
- No explanations
- No formatting

Input:
File: {filename}
Content:
\"\"\"
{content}
\"\"\"""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_context_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a structured data extractor.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Extract translation context.

Output language for VALUES: {target_language}

JSON SCHEMA:
{{
  "industry": "string",
  "tone": "string",
  "audience": "string",
  "keywords": ["string"],
  "entities": ["string"],
  "glossary": {{"source_term": "target_term"}}
}}

Rules:
- Output ONLY valid JSON
- No extra text
- All values MUST be in {target_language}
- Keep fields short and precise

Example:
{{
  "industry": "Restaurant SaaS",
  "tone": "Professional and friendly",
  "audience": "Restaurant owners",
  "keywords": ["POS", "orders"],
  "entities": ["Stripe"],
  "glossary": {{"order": "commande"}}
}}

Input:
File: {filename}
Base context: {base_context}

Content:
\"\"\"
{content}
\"\"\"""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_global_context_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a structured aggregator.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Merge multiple file contexts into ONE global context.

Output language: {target_language}

JSON SCHEMA:
{{
  "industry": "string",
  "tone": "string",
  "audience": "string",
  "keywords": ["string"],
  "entities": ["string"],
  "glossary": {{"source_term": "target_term"}},
  "summary": "string"
}}

Rules:
- Output ONLY valid JSON
- Merge duplicates
- Keep consistency
- All values in {target_language}

Input:
{compact_files}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_translation_draft_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a professional translation engine.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Translate the following list of strings from {source_language} to {target_language}.

Context:
- Industry: {industry}
- Summary: {summary}

Domain Rules:
{domain_rules}

Constraint Hierarchy (Priority 1 is most important):
1. MEANING: Preserve the original meaning exactly. No omissions or additions.
2. TECHNICAL: Preserve all placeholders ({{{{name}}}}, %s, :var, {{var}}), numbers, and brand names.
3. GLOSSARY: Use the provided glossary terms strictly.

Glossary:
{glossary}

Similar Translation Examples (Reference only):
{rag_examples}

Output:
Return ONLY a raw JSON array of translated strings.

Example:
["translated_text_1", "translated_text_2"]

Texts:
{texts}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_translation_refine_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a localization expert and senior editor in {target_language}.")
    human_msg = HumanMessagePromptTemplate.from_template("""Input: 
You are provided with a DRAFT translation in {target_language} that needs refinement for natural flow and professional impact.

Task:
Improve the fluency and style of the draft translations.

Constraint Hierarchy (Priority 1 is most important):
1. PRESERVATION: DO NOT change placeholders ({{{{name}}}}, %s, :var, {{var}}), numbers, or brand names.
2. MEANING: Keep the meaning unchanged. The translation must remain faithful to the original intent. DO NOT sacrifice accuracy for the sake of fluency or style.
3. STYLE: Adapt the text to the specified tone and audience to sound like a native professional.

Style Specifications:
- Tone: {tone}
- Audience: {audience}

Rules:
- Avoid literal translation, but ensure the core message remains identical to the source.
- Ensure natural phrasing in {target_language}.
- If the draft is already excellent, keep it as is.

Output:
Return ONLY a raw JSON array of refined strings.

Input (Draft Translations):
{draft_translations}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_json_repair_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a JSON repair tool.")
    human_msg = HumanMessagePromptTemplate.from_template("""Fix the output to be valid JSON.

Rules:
- Return ONLY valid JSON
- No explanation
- Keep content unchanged

Input:
{raw_output}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_validation_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a translation QA system.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Validate if the translation from {source_lang} to {target_lang} is correct, natural, and preserves all technical elements.

Input:
- Source ({source_lang}): "{source_text}"
- Translation ({target_lang}): "{translated_text}"

Criteria for is_valid=true:
1. The meaning is identical to the source.
2. All placeholders ({{{{name}}}}, %s, :var, {{var}}) are exactly the same as in the source.
3. No hallucinated content.
4. Fluency is natural for the target audience.

Output:
Return ONLY a valid JSON object. DO NOT include any explanation or extra text.

JSON Schema:
{{
  "is_valid": boolean,
  "error_type": "meaning|fluency|structure|placeholder|none",
  "reason": "short explanation in English"
}}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_fix_translation_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a senior translation editor specialized in {target_language}.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Fix the following translation from the source text. 

Source (Original):
"{source_text}"

Current Bad Translation ({target_language}):
"{bad_translation}"

Examples of correct behavior:
Example 1:
Source: "Settings"
Bad Translation: "Config"
Corrected Translation: "الإعدادات"

Example 2:
Source: "From the Inside Out"
Bad Translation: "Hallucinated interpretation"
Corrected Translation: "من الداخل إلى الخارج"

Instructions:
- Fix grammatical errors, fluency issues, or placeholder corruption.
- DO NOT translate the source back to English.
- DO NOT provide any explanation, commentary, or introduction.
- Return ONLY the corrected translation in {target_language}.

Corrected Translation:""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def build_batch_metadata(
    context: Dict[str, Any],
    size_margin_pct: float = 0.2,
) -> Dict[str, Any]:
    return {
        "tone": context.get("tone", ""),
        "audience": context.get("audience", ""),
        "glossary": context.get("glossary", {}),
        "entities": context.get("entities", []),
        "constraints": {
            "preserve_placeholders": True,
            "size_margin_pct": size_margin_pct,
        }
    }
