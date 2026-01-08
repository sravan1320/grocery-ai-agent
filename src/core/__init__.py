"""
Core module initialization.
"""

from .llm_engine import (
    parse_grocery_list_llm,
    compare_product_variants,
    reason_vendor_selection,
    handle_user_query,
    validate_llm_decision,
    select_best_variant_by_quantity,
    explain_variant_selection
)

from .retry_utils import (
    retry_with_backoff,
    RetryConfig,
    APIResponseValidator,
    TransientError,
    PermanentError,
    validate_llm_output
)

from .db import get_db_connection, init_database, import_csv_data

__all__ = [
    # LLM functions
    "parse_grocery_list_llm",
    # "compare_product_variants",
    "select_best_variant_by_quantity",
    "explain_variant_selection",
    "reason_vendor_selection",
    "handle_user_query",
    "validate_llm_decision",
    # Retry and validation
    "retry_with_backoff",
    "RetryConfig",
    "APIResponseValidator",
    "TransientError",
    "PermanentError",
    "validate_llm_output",
    # Database
    "get_db_connection",
    "init_database",
    "import_csv_data",
]
