"""
Simplified extractor for active Brazilian deputies
Fetches only essential data: name, party, state, contact info, and social media
"""

import requests
import logging
from typing import Dict, List, Optional
from django.db import transaction
from .models import Deputado
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeputadosDataExtractor:
    """
    Simplified extractor for active Brazilian deputies
    Fetches only essential contact and political information
    """
    
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def get_current_deputies(self):
        """
        Get all active deputies from current legislature
        """
        try:
            url = f"{self.base_url}/deputados"
            params = {
                'idLegislatura': 57,  # Current legislature (2023-2027)
                'ordem': 'ASC',
                'ordenarPor': 'nome'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('dados', [])
        except Exception as e:
            logger.error(f"Error fetching deputies: {str(e)}")
            return []
    
    def _is_official_camara_link(self, url: str) -> bool:
        """
        Check if a URL is from official Chamber of Deputies accounts
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # List of official Chamber identifiers (comprehensive patterns from old implementation)
        official_patterns = [
            'camaradeputados',
            'camara.leg.br',
            'camaradosdeputados',
            'UC-ZkSRh-7UEuwXJQ9UMCFJA',  # Official YouTube channel
            '/camaradeputados',
            '@camaradeputados',
            '@camaradosdeputados',
            'camaradeputados.leg.br',  # Additional patterns from old code
            'camaradeputados.com.br',
            'camaradeputados.org.br',
            'camara.net.br',
            'camaradeputados.net.br',
            'deputadoscamara',
            'camara-deputados',
            'camarabrasil',
            'congressonacional',
        ]
        
        return any(pattern.lower() in url_lower for pattern in official_patterns)
    
    def extract_social_media_links(self, deputado_id: int) -> Dict[str, str]:
        """
        Extract social media links from deputy's profile page
        """
        social_media = {
            'facebook': None,
            'twitter': None,
            'instagram': None,
            'youtube': None,
            'tiktok': None,
            'linkedin': None
        }
        
        try:
            # URL of deputy's page on Chamber website
            url = f"https://www.camara.leg.br/deputados/{deputado_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look specifically for Instagram links with class "username-insta"
            instagram_link = soup.find('a', class_='username-insta')
            if instagram_link and instagram_link.get('href'):
                instagram_url = instagram_link.get('href')
                if 'camaradeputados' not in instagram_url.lower():
                    social_media['instagram'] = instagram_url
            
            # If Instagram not found with specific class, try other strategies
            if not social_media['instagram']:
                # Look for section containing deputy-specific Instagram
                instagram_heading = soup.find('h3', string='INSTAGRAM') or soup.find('h4', string='INSTAGRAM')
                if instagram_heading:
                    # Find Instagram link near this heading
                    next_element = instagram_heading.find_next_sibling()
                    if next_element:
                        instagram_link = next_element.find('a', href=re.compile(r'instagram\.com'))
                        if instagram_link and 'camaradeputados' not in instagram_link.get('href', ''):
                            social_media['instagram'] = instagram_link.get('href')
            
            # If still no Instagram, search entire page with strict filters
            if not social_media['instagram']:
                all_instagram_links = soup.find_all('a', href=re.compile(r'instagram\.com'))
                for link in all_instagram_links:
                    href = link.get('href', '')
                    # Only accept if NOT the official Chamber link
                    if ('/camaradeputados' not in href and 
                        'camaradeputados' not in href and
                        not href.endswith('/camaradeputados')):
                        social_media['instagram'] = href
                        break  # Take only the first valid one
            
            # Look specifically for div with class "l-grid-social-media"
            social_media_div = soup.find('div', class_='l-grid-social-media')
            if social_media_div:
                logger.info(f"Found l-grid-social-media div for deputy {deputado_id}")
                
                # Look for social media widgets with data-url* attributes
                widgets = social_media_div.find_all('div', class_=lambda x: x and 'widget-' in x)
                
                for widget in widgets:
                    # Instagram widget
                    if 'widget-instagram' in widget.get('class', []):
                        instagram_handle = widget.get('data-urlinstagran') or widget.get('data-urlinstagram')
                        if instagram_handle and not social_media['instagram']:
                            # Build complete Instagram URL
                            if not instagram_handle.startswith('http'):
                                instagram_url = f"https://www.instagram.com/{instagram_handle.lstrip('@')}"
                            else:
                                instagram_url = instagram_handle
                            
                            if not self._is_official_camara_link(instagram_url):
                                social_media['instagram'] = instagram_url
                    
                    # Facebook widget
                    elif 'widget-facebook' in widget.get('class', []):
                        facebook_handle = widget.get('data-urlFacebook')
                        if facebook_handle and not social_media['facebook']:
                            if not facebook_handle.startswith('http'):
                                facebook_url = f"https://www.facebook.com/{facebook_handle}"
                            else:
                                facebook_url = facebook_handle
                            social_media['facebook'] = facebook_url
                    
                    # Twitter widget
                    elif 'widget-twitter' in widget.get('class', []):
                        twitter_handle = widget.get('data-urlTwitter')
                        if twitter_handle and not social_media['twitter']:
                            if not twitter_handle.startswith('http'):
                                twitter_url = f"https://twitter.com/{twitter_handle.lstrip('@')}"
                            else:
                                twitter_url = twitter_handle
                            social_media['twitter'] = twitter_url
                    
                    # YouTube widget
                    elif 'widget-youtube' in widget.get('class', []):
                        youtube_url = widget.get('data-urlYoutube')
                        if youtube_url and not social_media['youtube']:
                            # Check if it's not the official Chamber channel
                            if 'UC-ZkSRh-7UEuwXJQ9UMCFJA' not in youtube_url:
                                social_media['youtube'] = youtube_url
                    
                    # TikTok widget
                    elif 'widget-tiktok' in widget.get('class', []):
                        tiktok_handle = widget.get('data-urlTiktok')
                        if tiktok_handle and not social_media['tiktok']:
                            if not tiktok_handle.startswith('http'):
                                tiktok_url = f"https://www.tiktok.com/@{tiktok_handle.lstrip('@')}"
                            else:
                                tiktok_url = tiktok_handle
                            social_media['tiktok'] = tiktok_url
                    
                    # LinkedIn widget
                    elif 'widget-linkedin' in widget.get('class', []):
                        linkedin_url = widget.get('data-urlLinkedin')
                        if linkedin_url and not social_media['linkedin']:
                            social_media['linkedin'] = linkedin_url
                
                # Also check traditional links in the div
                social_links = social_media_div.find_all('a', href=True)
                
                for link in social_links:
                    href = link.get('href', '')
                    
                    # Use comprehensive filter for official links
                    if not self._is_official_camara_link(href):
                        if 'facebook.com' in href and not social_media['facebook']:
                            social_media['facebook'] = href
                        elif ('twitter.com' in href or 'x.com' in href) and not social_media['twitter']:
                            social_media['twitter'] = href
                        elif 'instagram.com' in href and not social_media['instagram']:
                            social_media['instagram'] = href
                        elif ('youtube.com' in href or 'youtu.be' in href) and not social_media['youtube']:
                            social_media['youtube'] = href
                        elif 'tiktok.com' in href and not social_media['tiktok']:
                            social_media['tiktok'] = href
                        elif 'linkedin.com' in href and not social_media['linkedin']:
                            social_media['linkedin'] = href
            
            # If still no social media found, search main content area
            if not any(social_media.values()):
                # Search within main content, not in footer/sidebar
                main_content = soup.find('main') or soup.find('div', class_='content') or soup.body
                if main_content:
                    links = main_content.find_all('a', href=True)
                    
                    for link in links:
                        href = link.get('href', '').lower()
                        full_href = link.get('href', '')
                        
                        # Check if not in footer area
                        parent_classes = []
                        parent = link.parent
                        while parent and parent.name:
                            if parent.get('class'):
                                parent_classes.extend(parent.get('class'))
                            parent = parent.parent
                        
                        # Skip if in footer/sidebar
                        if any('footer' in cls.lower() or 'rodape' in cls.lower() for cls in parent_classes):
                            continue
                        
                        # Facebook
                        if ('facebook.com' in href or 'fb.com' in href) and not social_media['facebook']:
                            if not self._is_official_camara_link(full_href):
                                social_media['facebook'] = full_href
                        
                        # Twitter/X  
                        elif ('twitter.com' in href or 'x.com' in href) and not social_media['twitter']:
                            if not self._is_official_camara_link(full_href):
                                social_media['twitter'] = full_href
                        
                        # Instagram
                        elif 'instagram.com' in href and not social_media['instagram']:
                            if not self._is_official_camara_link(full_href):
                                social_media['instagram'] = full_href
                        
                        # YouTube (with strict filters)
                        elif ('youtube.com' in href or 'youtu.be' in href) and not social_media['youtube']:
                            if not self._is_official_camara_link(full_href):
                                social_media['youtube'] = full_href
                        
                        # TikTok
                        elif 'tiktok.com' in href and not social_media['tiktok']:
                            if '@camaradosdeputados' not in href:
                                social_media['tiktok'] = full_href
                        
                        # LinkedIn
                        elif 'linkedin.com' in href and not social_media['linkedin']:
                            social_media['linkedin'] = full_href
            
            # Fallback: search entire page if no links found in main sections
            if not any(social_media.values()):
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href', '').lower()
                    
                    if 'facebook.com' in href and not social_media['facebook']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['facebook'] = link.get('href')
                    
                    elif ('twitter.com' in href or 'x.com' in href) and not social_media['twitter']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['twitter'] = link.get('href')
                    
                    elif 'instagram.com' in href and not social_media['instagram']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['instagram'] = link.get('href')
                    
                    elif ('youtube.com' in href or 'youtu.be' in href) and not social_media['youtube']:
                        full_href_for_check = link.get('href', '')
                        # Apply same strict filters as first search
                        is_official = ('UC-ZkSRh-7UEuwXJQ9UMCFJA' in full_href_for_check or 
                                     'camaradeputados' in href or
                                     'camara.leg.br' in href)
                        
                        if not is_official:
                            social_media['youtube'] = full_href_for_check
                    
                    elif 'tiktok.com' in href and not social_media['tiktok']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['tiktok'] = link.get('href')
                    
                    elif 'linkedin.com' in href and not social_media['linkedin']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['linkedin'] = link.get('href')
            
            # Log results
            found_links = [k for k, v in social_media.items() if v]
            if found_links:
                logger.info(f"Social media found for deputy {deputado_id}: {', '.join(found_links)}")
            else:
                logger.info(f"No social media found for deputy {deputado_id}")
                
            return social_media
            
        except Exception as e:
            logger.error(f"Error extracting social media for deputy {deputado_id}: {str(e)}")
            return social_media
    
    def extract_deputies(self, update_existing: bool = True, extract_social_media: bool = True):
        """
        Extract deputies data and save to database
        
        Args:
            update_existing: Update existing deputies with new data
            extract_social_media: Extract social media links (slower but more complete)
        
        Returns:
            tuple: (created_count, updated_count)
        """
        logger.info("Starting deputies data extraction...")
        
        deputies_data = self.get_current_deputies()
        if not deputies_data:
            logger.warning("No deputies data found")
            return 0, 0
        
        created_count = 0
        updated_count = 0
        
        with transaction.atomic():
            # First, mark all deputies as inactive
            Deputado.objects.all().update(is_active=False)
            
            for deputy_data in deputies_data:
                try:
                    api_id = deputy_data.get('id')  # API returns 'id', not 'api_id'
                    if not api_id:
                        continue
                    
                    # Extract social media if requested
                    social_media = {}
                    if extract_social_media:
                        logger.info(f"Extracting social media for {deputy_data.get('nome', 'Unknown')}...")
                        social_media = self.extract_social_media_links(api_id)
                        # Add delay to avoid overwhelming the server
                        time.sleep(1.5)
                    
                    # Get or create deputy
                    deputy, created = Deputado.objects.get_or_create(
                        api_id=api_id,
                        defaults={
                            'nome_parlamentar': deputy_data.get('nome', ''),
                            'partido': deputy_data.get('siglaPartido', ''),
                            'uf': deputy_data.get('siglaUf', ''),
                            'email': deputy_data.get('email'),
                            'foto_url': deputy_data.get('urlFoto'),
                            'facebook_url': social_media.get('facebook'),
                            'twitter_url': social_media.get('twitter'),
                            'instagram_url': social_media.get('instagram'),
                            'youtube_url': social_media.get('youtube'),
                            'tiktok_url': social_media.get('tiktok'),
                            'linkedin_url': social_media.get('linkedin'),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                        logger.info(f"Created: {deputy.nome_parlamentar}")
                        
                    elif update_existing:
                        # Update existing deputy
                        deputy.nome_parlamentar = deputy_data.get('nome', '')
                        deputy.partido = deputy_data.get('siglaPartido', '')
                        deputy.uf = deputy_data.get('siglaUf', '')
                        deputy.is_active = True
                        
                        if deputy_data.get('email'):
                            deputy.email = deputy_data['email']
                        
                        if deputy_data.get('urlFoto'):
                            deputy.foto_url = deputy_data['urlFoto']
                        
                        # Update social media if extracted
                        if extract_social_media:
                            deputy.facebook_url = social_media.get('facebook')
                            deputy.twitter_url = social_media.get('twitter')
                            deputy.instagram_url = social_media.get('instagram')
                            deputy.youtube_url = social_media.get('youtube')
                            deputy.tiktok_url = social_media.get('tiktok')
                            deputy.linkedin_url = social_media.get('linkedin')
                        
                        deputy.save()
                        updated_count += 1
                        logger.info(f"Updated: {deputy.nome_parlamentar}")
                    
                    else:
                        # Just mark as active
                        deputy.is_active = True
                        deputy.save()
                        
                except Exception as e:
                    deputy_name = deputy_data.get('nome', 'Unknown') if deputy_data else 'Unknown'
                    logger.error(f"Error processing deputy {deputy_name}: {str(e)}")
                    continue
        
        logger.info(f"Extraction completed: {created_count} created, {updated_count} updated")
        return created_count, updated_count
