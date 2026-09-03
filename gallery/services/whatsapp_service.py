import os
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger("kshan.whatsapp")

# Meta WhatsApp Cloud API Endpoint Format:
# https://graph.facebook.com/{META_WA_API_VERSION}/{META_WA_PHONE_NUMBER_ID}/messages

META_WA_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "")
META_WA_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "")
META_WA_API_VERSION = os.getenv("META_WA_API_VERSION", "v21.0")
META_WA_OTP_TEMPLATE_NAME = os.getenv("META_WA_OTP_TEMPLATE_NAME", "")  # e.g., 'kshan_auth_otp'

def normalize_phone_number(phone_str: str) -> str:
    """Normalizes phone number to digits only with country code (e.g. 919876543210)."""
    if not phone_str:
        return ""
    digits = "".join(ch for ch in phone_str if ch.isdigit())
    # If 10 digits (India standard), prepend 91
    if len(digits) == 10:
        digits = "91" + digits
    return digits

def send_whatsapp_otp(phone: str, otp_code: str) -> dict:
    """
    Sends a 6-digit OTP code to the specified phone number using Meta WhatsApp Cloud API.
    If credentials are not yet configured or in mock/dev mode, logs cleanly and returns success.
    """
    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        return {"success": False, "error": "Invalid phone number format."}

    phone_id = os.getenv("META_WA_PHONE_NUMBER_ID", META_WA_PHONE_NUMBER_ID)
    token = os.getenv("META_WA_ACCESS_TOKEN", META_WA_ACCESS_TOKEN)
    api_version = os.getenv("META_WA_API_VERSION", META_WA_API_VERSION)
    template_name = os.getenv("META_WA_OTP_TEMPLATE_NAME", META_WA_OTP_TEMPLATE_NAME)

    # Dev / Simulation mode if token or phone_id not provided
    if not phone_id or not token:
        logger.warning(
            f"[Meta WhatsApp Mock] Credentials not configured in .env. OTP for {normalized_phone} is: {otp_code}"
        )
        return {
            "success": True, 
            "mock": True,
            "message": f"[Dev Demo] OTP code is {otp_code}. (Configure META_WA_ACCESS_TOKEN in .env for live WhatsApp delivery)",
            "otp_code": otp_code
        }

    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Meta Cloud API message payload
    if template_name:
        # Template Message (Official WhatsApp Business Template)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": "en"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": otp_code
                            }
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": "0",
                        "parameters": [
                            {
                                "type": "text",
                                "text": otp_code
                            }
                        ]
                    }
                ]
            }
        }
    else:
        # Direct Text message payload (used for service conversations or test numbers)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": f"🔒 Your KSHAN Studio verification code is *{otp_code}*. Valid for 10 minutes. Please do not share this code with anyone."
            }
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        resp_data = response.json()
        if response.status_code in (200, 201):
            logger.info(f"Meta WhatsApp OTP sent successfully to {normalized_phone}: {resp_data}")
            return {"success": True, "data": resp_data}
        else:
            logger.error(f"Meta WhatsApp API Error ({response.status_code}): {resp_data}")
            error_msg = resp_data.get("error", {}).get("message", "Failed to send WhatsApp OTP")
            return {"success": False, "error": error_msg, "details": resp_data}
    except Exception as e:
        logger.error(f"Meta WhatsApp Request Exception: {e}")
        return {"success": False, "error": str(e)}
