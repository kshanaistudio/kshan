import logging
import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)

def get_razorpay_client():
    """Initializes and returns the Razorpay client."""
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not key_id or not key_secret:
        logger.warning("Razorpay credentials not fully configured in settings.")
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_in_rupees, currency="INR", receipt=None, notes=None):
    """
    Creates a Razorpay Order.
    amount_in_rupees: e.g. 49 or 1499.00
    Razorpay expects the amount in the smallest currency sub-unit (paise for INR).
    """
    client = get_razorpay_client()
    amount_paise = int(round(float(amount_in_rupees) * 100))
    
    order_payload = {
        "amount": amount_paise,
        "currency": currency or getattr(settings, 'RAZORPAY_CURRENCY', 'INR'),
        "payment_capture": 1, # Auto-capture
    }
    if receipt:
        order_payload["receipt"] = str(receipt)[:40]
    if notes and isinstance(notes, dict):
        order_payload["notes"] = notes

    try:
        order = client.order.create(data=order_payload)
        return order
    except Exception as e:
        logger.error(f"Failed to create Razorpay order: {e}", exc_info=True)
        raise e


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies the cryptographic HMAC SHA256 signature returned by Razorpay Checkout.
    Returns True if valid, False otherwise.
    """
    client = get_razorpay_client()
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.error(f"Razorpay signature verification failed for order {razorpay_order_id}, payment {razorpay_payment_id}")
        return False
    except Exception as e:
        logger.error(f"Error during signature verification: {e}", exc_info=True)
        return False
