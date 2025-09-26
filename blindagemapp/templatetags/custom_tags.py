from django import template
from ..models import TwitterMessage

register = template.Library()

@register.simple_tag
def get_available_messages(parliamentarian):
    """Get available Twitter messages for a parliamentarian"""
    messages = TwitterMessage.objects.filter(status='ready')
    
    # Filter messages based on parliamentarian type
    if hasattr(parliamentarian, '_meta'):
        model_name = parliamentarian._meta.model_name
        if model_name == 'deputado':
            messages = messages.filter(for_deputies=True)
        elif model_name == 'senador':
            messages = messages.filter(for_senators=True)
    
    # Further filter by targeting criteria if specified
    compatible_messages = []
    for message in messages:
        if message.can_be_sent_to_parliamentarian(parliamentarian):
            compatible_messages.append(message)
    
    return compatible_messages

@register.filter
def get_twitter_handle(twitter_url):
    """Extract Twitter handle from URL"""
    if not twitter_url:
        return ""
    
    # Remove trailing slash and get the last part
    handle = twitter_url.rstrip('/').split('/')[-1]
    return handle if handle != 'twitter.com' else ""