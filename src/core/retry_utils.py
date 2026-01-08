"""
Retry logic and API error handling with exponential backoff.
Handles transient failures and validates all API responses.
"""

import asyncio
import logging
import time
from typing import Callable, Any, Optional, TypeVar
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_backoff: float = 32.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff
        self.jitter = jitter
    
    def get_backoff_time(self, attempt: int) -> float:
        """Calculate backoff time for attempt number."""
        backoff = min(
            self.initial_backoff * (self.backoff_multiplier ** attempt),
            self.max_backoff
        )
        
        if self.jitter:
            import random
            backoff = backoff * (0.5 + random.random())
        
        return backoff


class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, vendor: str, retry_possible: bool = True):
        self.message = message
        self.vendor = vendor
        self.retry_possible = retry_possible
        super().__init__(self.message)


class TransientError(APIError):
    """Error that might be transient (temporary)."""
    pass


class PermanentError(APIError):
    """Error that won't be resolved by retrying."""
    
    def __init__(self, message: str, vendor: str):
        super().__init__(message, vendor, retry_possible=False)


def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig = None,
    error_handler: Optional[Callable[[Exception, int], None]] = None
) -> Callable[..., T]:
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        config: Retry configuration
        error_handler: Callback on errors
    
    Returns:
        Wrapped function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                return result
            
            except PermanentError as e:
                logger.error(f"Permanent error from {func.__name__}: {e.message}")
                raise
            
            except (TransientError, ConnectionError, TimeoutError) as e:
                last_exception = e
                
                if attempt < config.max_retries:
                    backoff = config.get_backoff_time(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {backoff:.2f} seconds..."
                    )
                    
                    if error_handler:
                        error_handler(e, attempt)
                    
                    time.sleep(backoff)
                else:
                    logger.error(f"All {config.max_retries + 1} attempts failed")
            
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                raise
        
        if last_exception:
            raise last_exception
        
        raise RuntimeError(f"Failed to execute {func.__name__}")
    
    return wrapper


async def retry_with_backoff_async(
    func: Callable[..., Any],
    config: RetryConfig = None,
    error_handler: Optional[Callable[[Exception, int], None]] = None
) -> Callable[..., Any]:
    """
    Decorator to retry async function with exponential backoff.
    """
    if config is None:
        config = RetryConfig()
    
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Async retry succeeded on attempt {attempt + 1}")
                return result
            
            except PermanentError as e:
                logger.error(f"Permanent error from {func.__name__}: {e.message}")
                raise
            
            except (TransientError, ConnectionError, TimeoutError) as e:
                last_exception = e
                
                if attempt < config.max_retries:
                    backoff = config.get_backoff_time(attempt)
                    logger.warning(
                        f"Async attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {backoff:.2f} seconds..."
                    )
                    
                    if error_handler:
                        error_handler(e, attempt)
                    
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"All {config.max_retries + 1} async attempts failed")
            
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                raise
        
        if last_exception:
            raise last_exception
        
        raise RuntimeError(f"Failed to execute async {func.__name__}")
    
    return wrapper


class APIResponseValidator:
    """Validates API responses before using them."""
    
    @staticmethod
    def validate_vendor_response(response: dict, vendor: str) -> bool:
        """
        Validate vendor API response structure.
        
        Args:
            response: API response dict
            vendor: Vendor name
        
        Returns:
            True if valid, raises exception otherwise
        """
        required_keys = {"product_name", "variants", "status"}
        
        if not isinstance(response, dict):
            raise PermanentError(f"Invalid response type: {type(response)}", vendor)
        
        if not all(k in response for k in required_keys):
            raise PermanentError(f"Missing required keys in response", vendor)
        
        if response.get("status") == "error":
            raise TransientError(
                f"API returned error: {response.get('error_message')}",
                vendor
            )
        
        if response.get("status") not in ["success", "no_results"]:
            raise PermanentError(f"Invalid status: {response.get('status')}", vendor)
        
        if not isinstance(response.get("variants"), list):
            raise PermanentError("Variants must be a list", vendor)
        
        # Validate each variant
        for variant in response.get("variants", []):
            required_variant_keys = {"brand", "weight", "unit", "price", "vendor"}
            if not all(k in variant for k in required_variant_keys):
                raise PermanentError("Invalid variant structure", vendor)
            
            if variant.get("price", 0) <= 0:
                raise PermanentError("Invalid price in variant", vendor)
        
        logger.info(f"Vendor response validation passed for {vendor}")
        return True
    
    @staticmethod
    def validate_product_variant(variant: dict) -> bool:
        """Validate individual product variant."""
        required_keys = {"vendor", "brand", "weight", "unit", "price"}
        
        if not all(k in variant for k in required_keys):
            return False
        
        if variant.get("price", 0) <= 0:
            return False
        
        if variant.get("weight", 0) <= 0:
            return False
        
        if not variant.get("unit"):
            return False
        
        return True


def validate_llm_output(output: dict, required_keys: list) -> bool:
    """
    Validate LLM output structure.
    """
    if not isinstance(output, dict):
        logger.error(f"LLM output is not a dict: {type(output)}")
        return False
    
    if not all(k in output for k in required_keys):
        logger.error(f"LLM output missing keys. Required: {required_keys}, Got: {list(output.keys())}")
        return False
    
    return True
