"""
Cloudflare Turnstile utility functions for bot protection
"""
import requests
import logging
from django.conf import settings
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def verify_turnstile_token(token: str, ip_address: Optional[str] = None) -> Dict:
    """
    Verify Turnstile token with Cloudflare API
    
    Args:
        token: The Turnstile token from the frontend
        ip_address: Client IP address (optional)
    
    Returns:
        Dictionary with verification results
    """
    if not token:
        return {
            'success': False,
            'error_codes': ['missing-input-response'],
            'message': 'Token is required'
        }
    
    if not settings.TURNSTILE_SECRET_KEY:
        logger.error("TURNSTILE_SECRET_KEY not configured")
        return {
            'success': False,
            'error_codes': ['missing-secret-key'],
            'message': 'Turnstile secret key not configured'
        }
    
    url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    
    data = {
        'secret': settings.TURNSTILE_SECRET_KEY,
        'response': token,
    }
    
    if ip_address:
        data['remoteip'] = ip_address
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('success'):
            logger.info(f"Turnstile verification successful for IP: {ip_address}")
        else:
            logger.warning(f"Turnstile verification failed for IP: {ip_address}, errors: {result.get('error-codes', [])}")
        
        return {
            'success': result.get('success', False),
            'error_codes': result.get('error-codes', []),
            'challenge_ts': result.get('challenge_ts'),
            'hostname': result.get('hostname'),
            'message': 'Verification successful' if result.get('success') else 'Verification failed'
        }
        
    except requests.exceptions.Timeout:
        logger.error("Turnstile verification timeout")
        return {
            'success': False,
            'error_codes': ['timeout-or-duplicate'],
            'message': 'Verification request timed out'
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Turnstile verification network error: {str(e)}")
        return {
            'success': False,
            'error_codes': ['network-error'],
            'message': 'Network error during verification'
        }
    except Exception as e:
        logger.error(f"Unexpected error during Turnstile verification: {str(e)}")
        return {
            'success': False,
            'error_codes': ['internal-error'],
            'message': 'Internal verification error'
        }


def get_client_ip(request) -> str:
    """
    Get client IP address from request
    
    Args:
        request: Django request object
    
    Returns:
        Client IP address as string
    """
    # Check for IP in various headers (for reverse proxy setups)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    
    return ip


def is_turnstile_verified(request) -> bool:
    """
    Check if the current session has been verified by Turnstile
    
    Args:
        request: Django request object
    
    Returns:
        True if verified, False otherwise
    """
    return request.session.get('turnstile_verified', False)


def mark_turnstile_verified(request) -> None:
    """
    Mark the current session as verified by Turnstile
    
    Args:
        request: Django request object
    """
    request.session['turnstile_verified'] = True
    request.session['turnstile_verified_ip'] = get_client_ip(request)


def clear_turnstile_verification(request) -> None:
    """
    Clear Turnstile verification from session
    
    Args:
        request: Django request object
    """
    request.session.pop('turnstile_verified', None)
    request.session.pop('turnstile_verified_ip', None)


def should_verify_turnstile(request) -> bool:
    """
    Determine if Turnstile verification is needed for this request
    
    Args:
        request: Django request object
    
    Returns:
        True if verification is needed, False otherwise
    """
    # Always require verification if not already verified
    if not is_turnstile_verified(request):
        return True
    
    # Check if IP has changed (potential session hijacking)
    verified_ip = request.session.get('turnstile_verified_ip')
    current_ip = get_client_ip(request)
    
    if verified_ip and verified_ip != current_ip:
        logger.warning(f"IP changed from {verified_ip} to {current_ip}, requiring re-verification")
        clear_turnstile_verification(request)
        return True
    
    return False