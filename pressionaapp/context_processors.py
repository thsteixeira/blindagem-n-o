"""
Context processors for making variables available in all templates
"""
from django.conf import settings

def turnstile_keys(request):
    """
    Make Turnstile site key available in all templates
    
    Args:
        request: Django request object
    
    Returns:
        Dictionary with Turnstile site key
    """
    return {
        'TURNSTILE_SITE_KEY': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
    }