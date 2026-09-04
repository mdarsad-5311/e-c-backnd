import logging
import razorpay
from razorpay.errors import SignatureVerificationError
from django.conf import settings

logger = logging.getLogger(__name__)


def get_razorpay_client() -> razorpay.Client:
    """
    Initializes and returns a Razorpay Client instance configured
    with key ID and key secret from django settings.
    """
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    return razorpay.Client(auth=(key_id, key_secret))


def verify_razorpay_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """
    Verifies Razorpay payment signature using HMAC SHA256.
    Returns True if valid, False if invalid or on verification error.
    """
    client = get_razorpay_client()
    params_dict = {
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    }
    try:
        client.utility.verify_payment_signature(params_dict)
        return True
    except SignatureVerificationError as e:
        logger.warning(f"Razorpay signature verification failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during signature verification: {e}")
        return False
