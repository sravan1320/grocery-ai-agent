"""
Vendor API utilities - centralized vendor API calls with retry logic.
"""

import logging
from typing import Optional
import requests

from models.api import VendorAPIResponse
from core.retry_utils import retry_with_backoff, TransientError, APIResponseValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# API configuration
VENDOR_API_BASE = "http://localhost:8000"


@retry_with_backoff
def fetch_from_zepto(product_name: str) -> Optional[VendorAPIResponse]:
    """Fetch product variants from Zepto."""
    try:
        logger.info(f"[VENDOR-API] Fetching from Zepto: {product_name}")
        response = requests.get(
            f"{VENDOR_API_BASE}/api/zepto/search",
            params={"product_name": product_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        APIResponseValidator.validate_vendor_response(data, "zepto")
        logger.info(f"[VENDOR-API] Zepto returned {len(data.get('variants', []))} variants")
        return VendorAPIResponse(**data)
    except requests.RequestException as e:
        logger.error(f"[VENDOR-API] Zepto API error: {str(e)}")
        raise TransientError(f"Zepto API error: {str(e)}", "zepto")


@retry_with_backoff
def fetch_from_blinkit(product_name: str) -> Optional[VendorAPIResponse]:
    """Fetch product variants from Blinkit."""
    try:
        logger.info(f"[VENDOR-API] Fetching from Blinkit: {product_name}")
        response = requests.get(
            f"{VENDOR_API_BASE}/api/blinkit/search",
            params={"product_name": product_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        APIResponseValidator.validate_vendor_response(data, "blinkit")
        logger.info(f"[VENDOR-API] Blinkit returned {len(data.get('variants', []))} variants")
        return VendorAPIResponse(**data)
    except requests.RequestException as e:
        logger.error(f"[VENDOR-API] Blinkit API error: {str(e)}")
        raise TransientError(f"Blinkit API error: {str(e)}", "blinkit")


@retry_with_backoff
def fetch_from_swiggy(product_name: str) -> Optional[VendorAPIResponse]:
    """Fetch product variants from Swiggy Instamart."""
    try:
        logger.info(f"[VENDOR-API] Fetching from Swiggy: {product_name}")
        response = requests.get(
            f"{VENDOR_API_BASE}/api/swiggy_instamart/search",
            params={"product_name": product_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        APIResponseValidator.validate_vendor_response(data, "swiggy_instamart")
        logger.info(f"[VENDOR-API] Swiggy returned {len(data.get('variants', []))} variants")
        return VendorAPIResponse(**data)
    except requests.RequestException as e:
        logger.error(f"[VENDOR-API] Swiggy API error: {str(e)}")
        raise TransientError(f"Swiggy API error: {str(e)}", "swiggy_instamart")


@retry_with_backoff
def fetch_from_bigbasket(product_name: str) -> Optional[VendorAPIResponse]:
    """Fetch product variants from BigBasket."""
    try:
        logger.info(f"[VENDOR-API] Fetching from BigBasket: {product_name}")
        response = requests.get(
            f"{VENDOR_API_BASE}/api/bigbasket/search",
            params={"product_name": product_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        APIResponseValidator.validate_vendor_response(data, "bigbasket")
        logger.info(f"[VENDOR-API] BigBasket returned {len(data.get('variants', []))} variants")
        return VendorAPIResponse(**data)
    except requests.RequestException as e:
        logger.error(f"[VENDOR-API] BigBasket API error: {str(e)}")
        raise TransientError(f"BigBasket API error: {str(e)}", "bigbasket")


def fetch_from_all_vendors(product_name: str) -> dict:
    """
    Fetch product from all vendors and aggregate results.
    
    Returns:
        {
            "zepto": VendorAPIResponse or None,
            "blinkit": VendorAPIResponse or None,
            "swiggy": VendorAPIResponse or None,
            "bigbasket": VendorAPIResponse or None
        }
    """
    logger.info(f"[VENDOR-API] Starting multi-vendor fetch for: {product_name}")
    
    results = {
        "zepto": None,
        "blinkit": None,
        "swiggy_instamart": None,
        "bigbasket": None
    }
    
    # Zepto
    try:
        results["zepto"] = fetch_from_zepto(product_name)
        logger.info(
            f"[VENDOR-API] Fetch summary for {product_name}: " +
            ", ".join(k for k, v in results.items() if v)
        )
    except Exception as e:
        logger.warning(f"[VENDOR-API] Zepto fetch failed: {e}")
    
    # Blinkit
    try:
        results["blinkit"] = fetch_from_blinkit(product_name)
        logger.info(
            f"[VENDOR-API] Fetch summary for {product_name}: " +
            ", ".join(k for k, v in results.items() if v)
        )
    except Exception as e:
        logger.warning(f"[VENDOR-API] Blinkit fetch failed: {e}")
    
    # Swiggy
    try:
        results["swiggy_instamart"] = fetch_from_swiggy(product_name)
        logger.info(
            f"[VENDOR-API] Fetch summary for {product_name}: " +
            ", ".join(k for k, v in results.items() if v)
        )
    except Exception as e:
        logger.warning(f"[VENDOR-API] Swiggy fetch failed: {e}")
    
    # BigBasket
    try:
        results["bigbasket"] = fetch_from_bigbasket(product_name)
        logger.info(
            f"[VENDOR-API] Fetch summary for {product_name}: " +
            ", ".join(k for k, v in results.items() if v)
        )
    except Exception as e:
        logger.warning(f"[VENDOR-API] BigBasket fetch failed: {e}")
    
    successful = sum(1 for v in results.values() if v is not None)
    logger.info(f"[VENDOR-API] Successfully fetched from {successful}/4 vendors")
        
    return results
