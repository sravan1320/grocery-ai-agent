"""
Ollama LLM integration for local reasoning and decision-making.
Uses Qwen 2.5 7B model with strict JSON output validation.
All LLM outputs must conform to Pydantic schemas.
"""

import ollama
import json
import logging
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_MODEL = "qwen2.5:7b" #"deepseek-r1:1.5b"
OLLAMA_HOST = "http://localhost:11434"

# System prompts for different tasks
PARSING_SYSTEM_PROMPT = """You are a grocery list parsing assistant. 
Parse the user's grocery list into structured JSON.
Extract: item_name, quantity, unit.
Return ONLY valid JSON, no markdown, no explanation."""

# COMPARISON_SYSTEM_PROMPT = """You are a product comparison expert.
# Compare product variants and recommend the best value option.
# Consider: price per unit, brand reputation, quantity efficiency.
# Return ONLY valid JSON with decision and justification."""

COMPARISON_SYSTEM_PROMPT = """
You are a shopping decision EXPLAINER.

A deterministic pricing engine has ALREADY selected the optimal variant.
You MUST NOT change the selection.

Your task:
1. Explain why this variant was selected
2. Mention price comparison clearly
3. If aggregation was used, explain savings
4. DO NOT suggest alternatives
5. DO NOT recompute price or quantity

Return ONLY valid JSON:
{
  "reason": "...",
  "confidence": 0.0-1.0
}
"""

REASONING_SYSTEM_PROMPT = """You are a logical reasoning expert for grocery shopping.
Make decisions about which products to buy considering vendor options.
Use deterministic reasoning, not speculation.
Return ONLY valid JSON with decision and confidence score."""

def select_best_variant_by_quantity(
    variants: list,
    requested_qty: float,
    requested_unit: str = "kg",
    dominance_threshold: float = 0.85
):
    """
    Deterministically decide between:
    - exact pack
    - aggregation of smaller packs
    """

    # Normalize all to kg
    normalized = []
    for v in variants:
        weight_kg = v.weight if v.unit == "kg" else v.weight / 1000
        price_per_kg = v.price / weight_kg
        normalized.append({
            "variant": v,
            "weight_kg": weight_kg,
            "price": v.price,
            "price_per_kg": price_per_kg
        })

    # 1️⃣ Best exact match (>= requested qty)
    exact_candidates = [
        n for n in normalized if n["weight_kg"] >= requested_qty
    ]

    best_exact = min(
        exact_candidates,
        key=lambda x: x["price"],
        default=None
    )

    # 2️⃣ Best aggregation option
    best_unit = min(normalized, key=lambda x: x["price_per_kg"])
    aggregate_price = best_unit["price_per_kg"] * requested_qty

    # 3️⃣ Decide
    if best_exact:
        if aggregate_price < best_exact["price"] * dominance_threshold:
            return {
                "strategy": "aggregation",
                "chosen": best_unit["variant"],
                "total_price": aggregate_price,
                "reason": "aggregation_cheaper"
            }
        else:
            return {
                "strategy": "exact_pack",
                "chosen": best_exact["variant"],
                "total_price": best_exact["price"],
                "reason": "exact_pack_preferred"
            }

    # 4️⃣ Fallback (no exact pack exists)
    return {
        "strategy": "aggregation",
        "chosen": best_unit["variant"],
        "total_price": aggregate_price,
        "reason": "no_exact_pack"
    }

def explain_variant_selection(
    product_name: str,
    decision: Dict[str, Any],
    requested_qty: float,
    requested_unit: str
) -> Optional[Dict[str, Any]]:
    """
    LLM EXPLAINS deterministic decision — does NOT choose.
    """

    prompt = f"""
    Product: {product_name}

    User requested: {requested_qty}{requested_unit}

    Final decision (DO NOT CHANGE):
    - Strategy: {decision['strategy']}
    - Brand: {decision['chosen'].brand}
    - Pack size: {decision['chosen'].weight}{decision['chosen'].unit}
    - Vendor: {decision['chosen'].vendor}
    - Total price: ₹{decision['total_price']}
    - Reason code: {decision['reason']}

    Explain clearly WHY this was chosen.
    """

    return call_ollama(prompt, COMPARISON_SYSTEM_PROMPT)


def parse_json_from_llm_output(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM output, handling markdown code blocks.
    """
    # Normalize and remove simple LLM thinking tags
    text = text.strip()
    text = re.sub(r'^<[^>]+>\s*', '', text)

    # 1) Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    candidate = None
    if json_match:
        candidate = json_match.group(1).strip()

    # 2) If no code block, try to parse the whole text
    if candidate is None:
        candidate = text

    # Helper: try parsing a candidate string as JSON
    def try_parse(s: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(s)
        except Exception:
            return None

    # Quick parse attempt
    parsed = try_parse(candidate)
    if parsed is not None:
        return parsed

    # 3) Try to find a JSON object or array via regex
    obj_match = re.search(r'(\{[\s\S]*\})', text)
    arr_match = re.search(r'(\[[\s\S]*\])', text)
    if obj_match:
        parsed = try_parse(obj_match.group(1))
        if parsed is not None:
            return parsed
    if arr_match:
        parsed = try_parse(arr_match.group(1))
        if parsed is not None:
            return parsed

    # 4) Robust bracket-matching extractor (walk from first brace and find matching closing)
    def extract_bracket_json(s: str) -> Optional[Dict[str, Any]]:
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            start = s.find(open_ch)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(s)):
                if s[i] == open_ch:
                    depth += 1
                elif s[i] == close_ch:
                    depth -= 1
                    if depth == 0:
                        candidate = s[start:i+1]
                        parsed = try_parse(candidate)
                        if parsed is not None:
                            return parsed
                        break
        return None

    parsed = extract_bracket_json(text)
    if parsed is not None:
        return parsed
    
    logger.info(f'parsed -> {parsed}')

    logger.error("Failed to parse JSON from LLM output (no valid JSON found).")
    logger.info(f"Output (truncated): {text[:500]}")
    return None


def call_ollama(prompt: str, system_prompt: str, json_schema: Optional[Type[BaseModel]] = None) -> Optional[Dict[str, Any]]:
    """
    Call Ollama with Qwen 2.5 7B model and validate output against schema.
    
    Args:
        prompt: User prompt
        system_prompt: System context
        json_schema: Pydantic model to validate against
    
    Returns:
        Validated JSON dict or None if validation failed
    """
    try:
        logger.info(f"Calling Ollama with prompt: {prompt[:100]}")
        
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            options={
                "temperature": 0.3,  # Lower temperature for deterministic output
                "top_p": 0.9,
                "top_k": 40,
            }
        )
        
        output_text = response['message']['content'].strip()
        logger.info(f"Ollama response: {output_text}")
        
        # Try to extract JSON
        json_data = parse_json_from_llm_output(output_text)
        
        if json_data is None:
            logger.error("Could not extract JSON from LLM output")
            return None
        
        # Validate against schema if provided
        if json_schema:
            try:
                validated = json_schema(**json_data)
                if validated is None:
                    return None
                logger.info(f"Validation successful for schema {json_schema.__name__}")
                return json.loads(validated.json())
            except ValidationError as e:
                logger.error(f"Schema validation failed: {e}")
                return None
        
        return json_data
    
    except Exception as e:
        logger.error(f"Ollama call failed: {str(e)}")
        return None


def parse_grocery_list_llm(user_input: str) -> Optional[Dict[str, Any]]:
    """
    Parse user's natural language grocery list into structured format.
    
    Returns JSON with structure:
    {
        "items": [
            {"item_name": "...", "quantity": 0.5, "unit": "kg"},
            ...
        ]
    }
    """
    prompt = f"""Parse this grocery list and return JSON:
    
User input: "{user_input}"

Return JSON with this structure:
{{
    "items": [
        {{"item_name": "product_name", "quantity": 0.5, "unit": "kg"}},
        ...
    ]
}}

Rules:
- Use lowercase, underscores for item names (e.g., "basmati_rice")
- Extract quantity and unit separately
- If no unit specified, use "pieces" for countable items
- If no quantity, assume 1"""
    
    return call_ollama(prompt, PARSING_SYSTEM_PROMPT)


def compare_product_variants(
    product_name: str,
    variants: list,
    quantity_needed: float,
    needed_unit: str
) -> Optional[Dict[str, Any]]:
    """
    Deterministic variant selection based on requested quantity.
    Handles exact-pack vs aggregation correctly.
    """

    decision = select_best_variant_by_quantity(
        variants=variants,
        requested_qty=quantity_needed,
        requested_unit=needed_unit
    )

    chosen = decision["chosen"]

    # return {
    #     "recommended_variant": {
    #         "brand": chosen.brand,
    #         "weight": chosen.weight,
    #         "unit": chosen.unit,
    #         "vendor": chosen.vendor,
    #         # 🔥 IMPORTANT: total price for requested quantity
    #         "price": decision["total_price"]
    #     },
    #     "strategy": decision["strategy"],
    #     "reason": decision["reason"],
    #     "confidence": 0.95
    # }
    return {
        "reason": decision["reason"],
        "confidence": 0.95
    }



def reason_vendor_selection(product_name: str, available_options: Dict[str, list], budget_constraints: Optional[Dict] = None, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Use LLM reasoning to select best vendor for product considering all factors.
    
    Args:
        product_name: Product to select vendor for
        available_options: Dict with vendor -> [variants]
        budget_constraints: Optional budget limits
        context: Optional context for modifications (user requirement, etc.)
    
    Returns JSON with structure:
    {
        "selected_vendor": "zepto",
        "selected_variant": {...},
        "reasoning": "...",
        "confidence": 0.95
    }
    """
    options_text = json.dumps({
        vendor: [
            {
                "brand": v.brand,
                "weight": v.weight,
                "unit": v.unit,
                "price": v.price
            }
            for v in variants
        ]
        for vendor, variants in available_options.items()
    }, indent=2)
    
    constraints_text = json.dumps(budget_constraints) if budget_constraints else "None"
    
    # ===== ENHANCED: Include user context if provided =====
    context_section = ""
    if context:
        user_requirement = context.get("user_requirement", "")
        current_selection = context.get("current_selection", {})
        modification_details = context.get("modification_details", {})
        
        context_section = f"""
    USER CONTEXT (Important for this selection):
    - User's specific requirement: "{user_requirement}"
    - Current selection in cart: {json.dumps(current_selection, indent=2)}
    - Modification details: {json.dumps(modification_details, indent=2)}

    TASK: Select the BEST option that matches the user's stated requirement above.
    The user has explicitly asked for this change, so prioritize matching their requirement.
    """
        
    prompt = f"""Select the best vendor for "{product_name}".

    Available options:
    {options_text}

    Budget constraints: {constraints_text}
    {context_section}

    Recommend the vendor that provides best value and matches the requirement.
    Consider: price, variety, brand options, user preference.

    Return JSON:
    {{
        "selected_vendor": "vendor_name",
        "selected_variant": {{
            "brand": "...",
            "weight": 0,
            "unit": "...",
            "price": 0.0
        }},
        "reasoning": "why this vendor/variant matches user's requirement",
        "confidence": 0.95
    }}"""
    
    return call_ollama(prompt, REASONING_SYSTEM_PROMPT)


def handle_user_query(query: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handle user follow-up questions about cart decisions.
    
    Returns JSON with:
    {
        "response": "...",
        "action": "none|modify_item|remove_item|recompare",
        "action_parameters": {...}
    }
    """
    context_text = json.dumps(context, indent=2, default=str)
    
    prompt = f"""User asked: "{query}"

Current cart context:
{context_text}

Understand the user's request and determine action needed.

Return JSON:
{{
    "response": "answer to user",
    "action": "none|modify_item|remove_item|recompare",
    "action_parameters": {{}}
}}"""
    
    system_prompt = "You are a helpful grocery shopping assistant. Respond to user questions about their shopping cart."
    
    return call_ollama(prompt, system_prompt)


def validate_llm_decision(decision: Dict[str, Any], decision_type: str) -> bool:
    """
    Validate LLM decision using deterministic checks before accepting it.
    
    Args:
        decision: LLM decision output
        decision_type: Type of decision (e.g., "variant_selection", "vendor_selection")
    
    Returns:
        True if decision is valid, False otherwise
    """
    try:
        if decision_type == "variant_selection":
            required_keys = {"brand", "weight", "unit", "vendor", "price", "reason"}
            if not all(k in decision.get("recommended_variant", {}) for k in required_keys):
                logger.error(f"Missing required keys in variant selection")
                return False
            
            if decision.get("price", 0) <= 0:
                logger.error(f"Invalid price in variant selection")
                return False
            
            if not (0 <= decision.get("confidence", 0) <= 1):
                logger.error(f"Invalid confidence score")
                return False
        
        elif decision_type == "vendor_selection":
            required_keys = {"selected_vendor", "reasoning"}
            if not all(k in decision for k in required_keys):
                logger.error(f"Missing required keys in vendor selection")
                return False
            
            if decision.get("selected_vendor") not in ["zepto", "blinkit", "swiggy_instamart", "bigbasket"]:
                logger.error(f"Invalid vendor name")
                return False
        
        logger.info(f"Decision validation passed for {decision_type}")
        return True
    
    except Exception as e:
        logger.error(f"Decision validation error: {str(e)}")
        return False
