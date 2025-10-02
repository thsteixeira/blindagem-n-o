"""
Cloudflare Turnstile middleware for bot protection
"""
import logging
from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.conf import settings
from .turnstile_utils import should_verify_turnstile

logger = logging.getLogger(__name__)

class TurnstileMiddleware:
    """
    Middleware to require Turnstile verification for all requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs that don't require Turnstile verification
        self.exempt_paths = [
            '/admin/',          # Django admin
            '/static/',         # Static files
            '/media/',          # Media files
            '/verify-turnstile/',  # Turnstile verification endpoint
            '/turnstile-challenge/',  # Turnstile challenge page
        ]
        
        # URL names that don't require verification
        self.exempt_url_names = [
            'admin:index',
            'admin:login',
            'verify_turnstile',
            'turnstile_challenge',
        ]

    def __call__(self, request):
        # Skip middleware if Turnstile is disabled (e.g., in development)
        if not getattr(settings, 'TURNSTILE_ENABLED', True):
            return self.get_response(request)
            
        # Skip middleware if Turnstile is not configured
        if not getattr(settings, 'TURNSTILE_SITE_KEY', None):
            logger.warning("Turnstile middleware active but TURNSTILE_SITE_KEY not configured")
            return self.get_response(request)
        
        # Check if path is exempt from verification
        if self._is_exempt_path(request):
            return self.get_response(request)
        
        # Check if Turnstile verification is needed
        if should_verify_turnstile(request):
            logger.info(f"Turnstile verification required for {request.path} from IP {self._get_client_ip(request)}")
            return render(request, 'pressionaapp/turnstile_challenge.html')
        
        # Continue with the request
        response = self.get_response(request)
        return response
    
    def _is_exempt_path(self, request):
        """
        Check if the request path is exempt from Turnstile verification
        """
        path = request.path
        
        # Check exempt paths
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return True
        
        # Check URL names
        try:
            from django.urls import resolve
            resolved = resolve(path)
            url_name = resolved.url_name
            
            if url_name in self.exempt_url_names:
                return True
                
            # Check for admin URLs
            if resolved.app_name == 'admin':
                return True
                
        except Exception:
            # If URL resolution fails, don't exempt
            pass
        
        return False
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class TurnstileLoggingMiddleware:
    """
    Optional middleware for logging Turnstile verification attempts
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Log successful verifications
        if hasattr(request, 'session') and request.session.get('turnstile_verified'):
            if not hasattr(request, '_turnstile_logged'):
                logger.info(f"Turnstile verified session accessing {request.path} from IP {self._get_client_ip(request)}")
                request._turnstile_logged = True
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip