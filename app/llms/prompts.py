"""
Prompt templates for every LLM call.

Each prompt pairs with a schema in app.llms.schemas and must be run through
llm.with_structured_output(<schema>, method="json_schema"), so the output
shape is enforced by the provider rather than described in the prompt text.
"""
from typing import Dict, Any
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

Output:
Put the paragraph in the summary field.

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

Rules:
- All values MUST be in {target_language}
- Keep fields short and precise
- entities: names that must not be translated (brands, products, services)
- glossary: domain terms with the translation that must be used for each

Example (French target):
- industry: Restaurant SaaS
- tone: Professional and friendly
- audience: Restaurant owners
- keywords: POS, orders
- entities: Stripe
- glossary: order -> commande

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

Rules:
- Merge duplicates
- Keep consistency
- All values in {target_language}

Input:
{compact_files}""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_translation_draft_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a professional translation engine.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Translate the following texts from {source_language} to {target_language}.

Context:
- Industry: {industry}
- Summary: {summary}

Domain Rules:
{domain_rules}

Constraint Hierarchy (Priority 1 is most important):
1. MEANING: Preserve the original meaning exactly. No omissions or additions.
2. TECHNICAL: Preserve all placeholders ({{{{name}}}}, %s, :var, {{{{var}}}}), numbers, and brand names.
3. FORMAT: If a text looks like a serialized JSON array (e.g. `["Item 1", "Item 2"]`), the translated string MUST remain a valid serialized JSON array.
4. GLOSSARY: Use the provided glossary terms strictly.

Glossary:
{glossary}

Similar Translation Examples (Reference only):
{rag_examples}

Output:
{output_instructions}

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
Put the refined strings in the translations field, one per draft, in the same order as the input.

Input (Draft Translations):
{draft_translations}""")
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
- is_valid: true only if every criterion above is met
- error_type: the main problem found, or none when the translation is valid
- reason: short explanation in English""")
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
- If the source text is a stringified JSON array (e.g. `["a", "b"]`), the corrected translation MUST also be a stringified JSON array.
- DO NOT translate the source back to English.
- Put only the corrected translation in {target_language} in the corrected_translation field, with no explanation or commentary.""")
    return ChatPromptTemplate.from_messages([system_msg, human_msg])


def get_complexity_rating_prompt() -> ChatPromptTemplate:
    system_msg = SystemMessagePromptTemplate.from_template("You are a translation complexity assessor.")
    human_msg = HumanMessagePromptTemplate.from_template("""Task:
Rate the translation complexity of the text from 0 to 100, where 100 is highly complex.

Consider idioms, ambiguity, domain jargon, placeholders or markup, and sentence structure.

Text:
\"\"\"
{text}
\"\"\"""")
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
