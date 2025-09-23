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
import random
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleSocialMediaSearcher:
    """Fallback search using Google to find deputy social media when not found on official pages."""
    
    def __init__(self):
        self.driver = None
        self.social_media_patterns = [
            (r'instagram\.com/([^/\s?]+)', 'instagram'),
            (r'twitter\.com/([^/\s?]+)', 'twitter'),
            (r'x\.com/([^/\s?]+)', 'twitter'),
            (r'facebook\.com/([^/\s?]+)', 'facebook'),
        ]
    
    def _setup_driver(self):
        """Set up headless Chrome WebDriver with anti-detection measures."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Run in background
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1366,768')  # More common resolution
            
            # Better user agent (more recent Chrome version)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
            
            # Anti-detection measures
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Suppress common Chrome automation errors
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-web-resources')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--log-level=3')  # Only show fatal errors
            
            # Use webdriver-manager to automatically download and manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            return True
        except WebDriverException as e:
            logger.error(f"Failed to setup Chrome WebDriver: {e}")
            return False
    
    def _cleanup_driver(self):
        """Cleanup WebDriver resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison by removing accents and converting to lowercase."""
        import unicodedata
        # Remove accents and normalize
        normalized = unicodedata.normalize('NFD', name.lower())
        ascii_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Remove common prefixes and suffixes
        ascii_name = re.sub(r'\b(dr|dra|prof|profª|professor|professora|sr|sra|deputado|deputada)\b\.?\s*', '', ascii_name)
        return ascii_name.strip()
    
    def _extract_name_parts(self, nome: str, nome_parlamentar: str) -> Dict[str, List[str]]:
        """Extract different parts of deputy's name for matching."""
        # Normalize names
        full_name = self._normalize_name(nome)
        parliamentary_name = self._normalize_name(nome_parlamentar)
        
        # Split into parts
        full_parts = [p for p in full_name.split() if len(p) > 2]  # Ignore short words like "de", "da"
        parl_parts = [p for p in parliamentary_name.split() if len(p) > 2]
        
        # Get first and last names
        first_name = full_parts[0] if full_parts else ""
        last_name = full_parts[-1] if len(full_parts) > 1 else ""
        
        # Get parliamentary first and last
        parl_first = parl_parts[0] if parl_parts else ""
        parl_last = parl_parts[-1] if len(parl_parts) > 1 else ""
        
        return {
            'full_parts': full_parts,
            'parl_parts': parl_parts,
            'first_name': first_name,
            'last_name': last_name,
            'parl_first': parl_first,
            'parl_last': parl_last,
            'all_significant': list(set(full_parts + parl_parts))  # Unique significant parts
        }
    
    def _calculate_url_confidence(self, url: str, name_parts: Dict[str, List[str]], platform: str) -> tuple:
        """
        Calculate confidence score for a social media URL based on name matching.
        Returns (confidence_level, needs_review, score_details)
        """
        url_lower = url.lower()
        
        # Extract username from URL
        username = ""
        if platform == 'instagram':
            match = re.search(r'instagram\.com/([^/\s?]+)', url_lower)
        elif platform == 'twitter':
            match = re.search(r'(?:twitter|x)\.com/([^/\s?]+)', url_lower) 
        elif platform == 'facebook':
            match = re.search(r'facebook\.com/([^/\s?]+)', url_lower)
        else:
            match = None
            
        if match:
            username = match.group(1).lower()
        
        score = 0
        details = []
        
        # Check for exact name matches
        for name_part in name_parts['all_significant']:
            if name_part in username:
                score += 3
                details.append(f"Name part '{name_part}' found in username")
        
        # Check for first+last name combination
        first = name_parts['first_name']
        last = name_parts['last_name']
        if first and last:
            if first in username and last in username:
                score += 5
                details.append(f"Both first name '{first}' and last name '{last}' found")
        
        # Check for parliamentary name parts
        parl_first = name_parts['parl_first'] 
        parl_last = name_parts['parl_last']
        if parl_first and parl_first in username:
            score += 2
            details.append(f"Parliamentary first name '{parl_first}' found")
        if parl_last and parl_last in username:
            score += 2  
            details.append(f"Parliamentary last name '{parl_last}' found")
        
        # Check for official keywords that increase confidence
        official_keywords = ['deputado', 'deputada', 'oficial', 'brazil', 'brasil', 'congresso', 'camara']
        for keyword in official_keywords:
            if keyword in username or keyword in url_lower:
                score += 2
                details.append(f"Official keyword '{keyword}' found")
        
        # Check for suspicious patterns that decrease confidence
        suspicious_patterns = [
            r'\d{4,}',  # Long numbers (likely fan accounts)
            r'fan|fans',  # Fan account indicators
            r'fake|falso',  # Fake account indicators  
            r'parody|parodia',  # Parody accounts
            r'_br$|brazil$',  # Generic suffixes
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, username):
                score -= 3
                details.append(f"Suspicious pattern '{pattern}' found (reduces confidence)")
        
        # Determine confidence level and review need
        if score >= 8:
            confidence = "high"
            needs_review = False
        elif score >= 4:
            confidence = "medium" 
            needs_review = True  # Medium confidence needs manual review
        else:
            confidence = "low"
            needs_review = True
        
        return confidence, needs_review, {
            'score': score,
            'username': username,
            'details': details
        }
    
    def _should_accept_url(self, url: str, name_parts: Dict[str, List[str]], platform: str) -> tuple:
        """
        Determine if a URL should be accepted based on smart filtering.
        Returns (should_accept, confidence, needs_review, details)
        """
        confidence, needs_review, score_details = self._calculate_url_confidence(url, name_parts, platform)
        
        # Reject low confidence URLs entirely (too risky)
        if confidence == "low":
            return False, confidence, needs_review, score_details
        
        # Accept medium and high confidence URLs
        return True, confidence, needs_review, score_details
    
    def _search_google(self, query: str) -> List[str]:
        """Search Google and return URLs from results."""
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            logger.info(f"Navigating to: {search_url}")
            self.driver.get(search_url)
            
            # Check if Google is showing CAPTCHA or blocking
            page_source = self.driver.page_source.lower()
            if 'captcha' in page_source or 'blocked' in page_source:
                logger.warning(f"Google may be blocking automated requests for: {query}")
                return []
            
            # Try multiple selectors for search results (Google changes these frequently)
            result_selectors = [
                # Modern Google selectors
                "div.g a[href]",              # Classic div.g structure
                "div[data-result-index] a[href]",  # Data-result-index structure
                ".tF2Cxc a[href]",           # Newer class name
                "h3 a[href]",                # Direct h3 links
                "[data-ved] a[href]",        # Data-ved attributes
                ".yuRUbf a[href]",           # Another modern selector
                ".kCrYT a[href]",            # Alternative structure
                "a[ping][href^='http']",     # Links with ping attribute
                # Fallback - any link that looks like a result
                "a[href*='instagram.com']",
                "a[href*='twitter.com']", 
                "a[href*='facebook.com']",
                "a[href*='youtube.com']"
            ]
            
            urls = []
            found_elements = False
            
            # Try each selector until we find results
            for selector in result_selectors:
                try:
                    # Wait for elements with this selector
                    WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    result_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Found {len(result_elements)} elements with selector: {selector}")
                    
                    if result_elements:
                        found_elements = True
                        for element in result_elements[:20]:  # Limit to first 20 results
                            try:
                                url = element.get_attribute('href')
                                if url and url.startswith('http') and 'google.com' not in url and 'googleusercontent.com' not in url:
                                    urls.append(url)
                            except Exception as e:
                                continue
                        
                        if urls:  # If we found URLs with this selector, use them
                            break
                            
                except TimeoutException:
                    continue  # Try next selector
            
            if not found_elements:
                logger.warning(f"No search result elements found for query: {query}")
                logger.info("Page title: " + self.driver.title)
                
                # Last resort: get all links and filter
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                logger.info(f"Found {len(all_links)} total links on page")
                
                for link in all_links:
                    try:
                        url = link.get_attribute('href')
                        if (url and url.startswith('http') and 
                            'google.com' not in url and 
                            'googleusercontent.com' not in url and
                            any(platform in url.lower() for platform in ['instagram', 'twitter', 'facebook', 'youtube', 'tiktok', 'linkedin'])):
                            urls.append(url)
                    except Exception:
                        continue
            
            unique_urls = list(dict.fromkeys(urls))  # Remove duplicates while preserving order
            logger.info(f"Found {len(unique_urls)} unique URLs for query: {query}")
            
            # Log first few URLs for debugging
            for i, url in enumerate(unique_urls[:5]):
                logger.info(f"  URL {i+1}: {url}")
            
            return unique_urls
            
        except TimeoutException:
            logger.warning(f"Timeout searching Google for: {query}")
            logger.info(f"Current page title: {self.driver.title if self.driver else 'N/A'}")
            return []
        except Exception as e:
            logger.error(f"Error searching Google for '{query}': {e}")
            return []
    
    def _extract_social_links_from_urls(self, urls: List[str]) -> Dict[str, str]:
        """Extract social media links from a list of URLs."""
        social_links = {}
        
        for url in urls:
            for pattern, platform in self.social_media_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    if platform not in social_links:
                        # Clean up the URL to get just the profile
                        clean_url = self._clean_social_media_url(url, platform)
                        social_links[platform] = clean_url
                    break
        
        return social_links
    
    def _clean_social_media_url(self, url: str, platform: str) -> str:
        """Clean social media URL to get just the profile URL."""
        # Remove query parameters and fragments first
        clean_url = url.split('?')[0].split('#')[0]
        
        if platform == 'twitter':
            # Twitter/X: Remove everything after username
            # https://twitter.com/username/status/123 -> https://twitter.com/username
            # https://x.com/username/with/123 -> https://x.com/username
            if '/status/' in clean_url or '/with/' in clean_url or '/photo/' in clean_url:
                parts = clean_url.split('/')
                if len(parts) >= 4:  # ['https:', '', 'twitter.com', 'username', ...]
                    clean_url = '/'.join(parts[:4])  # Keep only https://twitter.com/username
        
        elif platform == 'instagram':
            # Instagram: Remove everything after username
            # https://instagram.com/username/p/ABC123 -> https://instagram.com/username
            # https://instagram.com/username/reel/XYZ -> https://instagram.com/username
            if '/p/' in clean_url or '/reel/' in clean_url or '/tv/' in clean_url:
                parts = clean_url.split('/')
                if len(parts) >= 4:  # ['https:', '', 'instagram.com', 'username', ...]
                    clean_url = '/'.join(parts[:4])  # Keep only https://instagram.com/username
        
        elif platform == 'facebook':
            # Facebook: Remove everything after page name or ID
            # https://facebook.com/username/posts/123 -> https://facebook.com/username
            # https://facebook.com/username/photos/456 -> https://facebook.com/username
            if '/posts/' in clean_url or '/photos/' in clean_url or '/videos/' in clean_url:
                parts = clean_url.split('/')
                if len(parts) >= 4:  # ['https:', '', 'facebook.com', 'username', ...]
                    clean_url = '/'.join(parts[:4])  # Keep only https://facebook.com/username
        
        # Ensure URL ends without trailing slash (except for root)
        if clean_url.endswith('/') and clean_url.count('/') > 3:
            clean_url = clean_url.rstrip('/')
        
        return clean_url
    
    def search_deputy_social_media(self, nome: str, nome_parlamentar: str, role: str = "deputado") -> Dict[str, dict]:
        """
        Search for congress member social media accounts using Google with false positive detection.
        
        Args:
            nome: Full name of the congress member
            nome_parlamentar: Parliamentary name of the congress member
            role: Role of the person ("deputado" or "senador")
            
        Returns:
            Dictionary with platform names as keys and dictionaries containing URL and confidence info
        """
        if not self._setup_driver():
            return {}
        
        try:
            # Extract name parts for confidence scoring
            name_parts = self._extract_name_parts(nome, nome_parlamentar)
            
            all_social_links = {}
            confidence_info = {}
            
            # Try different search queries - LIMITED to most important platforms
            search_queries = [
                f'"{nome_parlamentar}" {role} instagram',
                f'"{nome_parlamentar}" {role} twitter',
                f'"{nome_parlamentar}" {role} facebook',
            ]
            
            for query in search_queries:
                logger.info(f"Searching Google: {query}")
                urls = self._search_google(query)
                
                if urls:
                    social_links = self._extract_social_links_from_urls(urls)
                    
                    # Apply false positive detection to each found link
                    for platform, url in social_links.items():
                        if platform not in all_social_links:  # Don't overwrite if we already found one
                            should_accept, confidence, needs_review, details = self._should_accept_url(
                                url, name_parts, platform
                            )
                            
                            if should_accept:
                                all_social_links[platform] = {
                                    'url': url,
                                    'confidence': confidence,
                                    'needs_review': needs_review,
                                    'score_details': details,
                                    'source': 'google_search'
                                }
                                logger.info(f"Accepted {platform} URL with {confidence} confidence: {url}")
                                if details['details']:
                                    logger.info(f"  Reasons: {'; '.join(details['details'])}")
                            else:
                                logger.warning(f"Rejected {platform} URL due to low confidence: {url}")
                                if details['details']:
                                    logger.warning(f"  Reasons: {'; '.join(details['details'])}")
                
                # Stop if we found accounts for all 3 major platforms
                if len(all_social_links) >= 3:  # Instagram, Twitter, Facebook
                    break
            
            if all_social_links:
                logger.info(f"Found {len(all_social_links)} social media accounts for {nome_parlamentar} via Google search")
            else:
                logger.info(f"No social media accounts found for {nome_parlamentar} via Google search")
            
            return all_social_links
        
        finally:
            self._cleanup_driver()


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
    
    def extract_social_media_links(self, deputado_id: int, nome: str = None, nome_parlamentar: str = None, use_google_fallback: bool = False) -> Dict[str, any]:
        """
        Extract social media links from deputy's profile page with metadata
        
        Returns:
            Dictionary containing social media URLs and metadata including source and confidence info
        """
        social_media = {
            'facebook': None,
            'twitter': None,
            'instagram': None,
            'youtube': None,
            'tiktok': None,
            'linkedin': None
        }
        
        # Metadata to track source and confidence
        metadata = {
            'source': None,
            'confidence': None,
            'needs_review': False,
            'details': None
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
            
            # Log results from Chamber website
            found_links = [k for k, v in social_media.items() if v]
            if found_links:
                logger.info(f"Social media found for deputy {deputado_id}: {', '.join(found_links)}")
                metadata = {
                    'source': 'chamber_website',
                    'confidence': 'high',
                    'needs_review': False,
                    'details': f"Found from official Chamber website: {', '.join(found_links)}"
                }
            else:
                logger.info(f"No social media found for deputy {deputado_id} on Chamber website")
            
            # Google search fallback if enabled and no social media found
            if use_google_fallback and not any(social_media.values()) and nome and nome_parlamentar:
                logger.info(f"Attempting Google search fallback for deputy {nome_parlamentar}")
                try:
                    google_searcher = GoogleSocialMediaSearcher()
                    google_results = google_searcher.search_deputy_social_media(nome, nome_parlamentar)
                    
                    # Process Google results with confidence information
                    if google_results:
                        # Merge Google results with existing (empty) social_media dict
                        for platform, result_data in google_results.items():
                            if platform in social_media and not social_media[platform]:
                                social_media[platform] = result_data['url']
                        
                        # Set overall metadata based on Google results
                        confidences = [result_data['confidence'] for result_data in google_results.values()]
                        needs_reviews = [result_data['needs_review'] for result_data in google_results.values()]
                        
                        # Determine overall confidence (use lowest)
                        if 'low' in confidences:
                            overall_confidence = 'low'
                        elif 'medium' in confidences:
                            overall_confidence = 'medium'  
                        else:
                            overall_confidence = 'high'
                        
                        overall_needs_review = any(needs_reviews)
                        
                        metadata = {
                            'source': 'google_search',
                            'confidence': overall_confidence,
                            'needs_review': overall_needs_review,
                            'details': f"Google search found: {list(google_results.keys())}",
                            'google_results': google_results  # Include detailed results
                        }
                        
                        # Log Google search results
                        google_found = list(google_results.keys())
                        logger.info(f"Google search found social media for {nome_parlamentar}: {', '.join(google_found)}")
                        logger.info(f"Overall confidence: {overall_confidence}, needs review: {overall_needs_review}")
                
                except Exception as e:
                    logger.error(f"Google search fallback failed for {nome_parlamentar}: {str(e)}")
            
            return {
                'social_media': social_media,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error extracting social media for deputy {deputado_id}: {str(e)}")
            return social_media
    
    def extract_deputies(self, update_existing: bool = True, extract_social_media: bool = True, use_google_fallback: bool = False, limit: int = None):
        """
        Extract deputies data and save to database
        
        Args:
            update_existing: Update existing deputies with new data
            extract_social_media: Extract social media links (slower but more complete)
            use_google_fallback: Use Google search as fallback when no social media found on Chamber website
            limit: Limit number of deputies to process (for testing)
        
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
        
        # Apply limit if specified
        if limit:
            deputies_data = deputies_data[:limit]
            logger.info(f"Processing limited to {limit} deputies")
        
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
                    metadata = {}
                    if extract_social_media:
                        nome = deputy_data.get('nome', '')
                        nome_parlamentar = deputy_data.get('nome', '')  # Use same as full name for now
                        logger.info(f"Extracting social media for {nome_parlamentar}...")
                        extraction_result = self.extract_social_media_links(
                            api_id, 
                            nome=nome, 
                            nome_parlamentar=nome_parlamentar, 
                            use_google_fallback=use_google_fallback
                        )
                        social_media = extraction_result.get('social_media', {})
                        metadata = extraction_result.get('metadata', {})
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
                            'social_media_source': metadata.get('source'),
                            'social_media_confidence': metadata.get('confidence'),
                            'needs_social_media_review': metadata.get('needs_review', False),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                        if metadata.get('source'):
                            logger.info(f"Created: {deputy.nome_parlamentar} (Social media source: {metadata.get('source')}, confidence: {metadata.get('confidence', 'N/A')}, needs review: {metadata.get('needs_review', False)})")
                        else:
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
                            deputy.social_media_source = metadata.get('source')
                            deputy.social_media_confidence = metadata.get('confidence')
                            deputy.needs_social_media_review = metadata.get('needs_review', False)
                        
                        deputy.save()
                        updated_count += 1
                        if metadata.get('source'):
                            logger.info(f"Updated: {deputy.nome_parlamentar} (Social media source: {metadata.get('source')}, confidence: {metadata.get('confidence', 'N/A')}, needs review: {metadata.get('needs_review', False)})")
                        else:
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
