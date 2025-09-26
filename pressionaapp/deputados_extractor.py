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


class TwitterSearcher:
    """Search engine for finding deputy Twitter accounts and extracting latest tweets."""
    
    def __init__(self):
        self.driver = None
        self.twitter_patterns = [
            (r'twitter\.com/([^/\s?]+)', 'twitter'),
            (r'x\.com/([^/\s?]+)', 'twitter'),
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
            
            # Additional options to suppress GPU/WebGL and DSH messages
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--disable-gpu-sandbox')
            
            # Suppress Chrome's internal messages completely (combine all excludeSwitches)
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Use webdriver-manager to automatically download and manage ChromeDriver
            # Suppress ChromeDriver logs as well
            service = Service(
                ChromeDriverManager().install(),
                log_level=0,  # Suppress all ChromeDriver logs
                service_args=['--silent']
            )
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
    
    def _extract_twitter_links_from_urls(self, urls: List[str]) -> List[str]:
        """Extract Twitter links from a list of URLs."""
        twitter_links = []
        
        for url in urls:
            for pattern, platform in self.twitter_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    # Clean up the URL to get just the profile
                    clean_url = self._clean_twitter_url(url)
                    if clean_url and clean_url not in twitter_links:
                        twitter_links.append(clean_url)
                    break
        
        return twitter_links
    
    def _clean_twitter_url(self, url: str) -> str:
        """Clean Twitter URL to get just the profile URL."""
        # Remove query parameters and fragments first
        clean_url = url.split('?')[0].split('#')[0]
        
        # Twitter/X: Remove everything after username
        # https://twitter.com/username/status/123 -> https://twitter.com/username
        # https://x.com/username/with/123 -> https://x.com/username
        if '/status/' in clean_url or '/with/' in clean_url or '/photo/' in clean_url:
            parts = clean_url.split('/')
            if len(parts) >= 4:  # ['https:', '', 'twitter.com', 'username', ...]
                clean_url = '/'.join(parts[:4])  # Keep only https://twitter.com/username
        
        # Ensure URL ends without trailing slash (except for root)
        if clean_url.endswith('/') and clean_url.count('/') > 3:
            clean_url = clean_url.rstrip('/')
        
        return clean_url
    
    def search_twitter_account(self, nome: str, nome_parlamentar: str, role: str = "deputado") -> Optional[Dict[str, any]]:
        """
        Search for congress member Twitter account using Google with false positive detection.
        
        Args:
            nome: Full name of the congress member
            nome_parlamentar: Parliamentary name of the congress member
            role: Role of the person ("deputado" or "senador")
            
        Returns:
            Dictionary with Twitter URL and confidence info, or None if not found
        """
        if not self._setup_driver():
            return None
        
        try:
            # Extract name parts for confidence scoring
            name_parts = self._extract_name_parts(nome, nome_parlamentar)
            
            # Twitter-specific search queries
            search_queries = [
                f'"{nome_parlamentar}" {role} twitter',
                f'"{nome_parlamentar}" {role} "x.com"',
                f'"{nome_parlamentar}" {role} site:twitter.com',
                f'"{nome}" {role} twitter',
            ]
            
            for query in search_queries:
                logger.info(f"Searching Google for Twitter: {query}")
                urls = self._search_google(query)
                
                if urls:
                    twitter_links = self._extract_twitter_links_from_urls(urls)
                    
                    # Apply false positive detection to each found Twitter link
                    for twitter_url in twitter_links:
                        should_accept, confidence, needs_review, details = self._should_accept_url(
                            twitter_url, name_parts, 'twitter'
                        )
                        
                        if should_accept:
                            result = {
                                'url': twitter_url,
                                'confidence': confidence,
                                'needs_review': needs_review,
                                'score_details': details,
                                'source': 'google_search'
                            }
                            logger.info(f"Found Twitter account with {confidence} confidence: {twitter_url}")
                            if details['details']:
                                logger.info(f"  Reasons: {'; '.join(details['details'])}")
                            
                            return result
                        else:
                            logger.warning(f"Rejected Twitter URL due to low confidence: {twitter_url}")
                            if details['details']:
                                logger.warning(f"  Reasons: {'; '.join(details['details'])}")
            
            logger.info(f"No Twitter account found for {nome_parlamentar} via Google search")
            return None
        
        finally:
            self._cleanup_driver()
    
    def extract_latest_tweet_url(self, twitter_url: str) -> Optional[str]:
        """
        Extract the URL of the latest tweet from a Twitter profile.
        Only works with public profiles (no authentication).
        
        Args:
            twitter_url: The Twitter/X profile URL
            
        Returns:
            URL of the latest tweet or None if not found
        """
        if not twitter_url or not self._setup_driver():
            return None
        
        try:
            # Navigate to the Twitter profile
            self.driver.get(twitter_url)
            
            # Wait a bit for the page to load
            time.sleep(3)
            
            # Try different selectors for tweets (Twitter changes these frequently)
            tweet_selectors = [
                'article[data-testid="tweet"]',  # Common tweet container
                'div[data-testid="tweet"]',      # Alternative tweet container
                '[data-testid="tweet"]',         # Any element with tweet testid
                'article[role="article"]',       # Generic article role
                'div[dir="auto"] a[href*="/status/"]'  # Direct status link approach
            ]
            
            latest_tweet_url = None
            
            for selector in tweet_selectors:
                try:
                    # Look for tweet elements
                    tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if tweet_elements:
                        # Get the first tweet (should be the latest)
                        first_tweet = tweet_elements[0]
                        
                        # Try to find a link to the tweet within this element
                        status_links = first_tweet.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
                        
                        if status_links:
                            href = status_links[0].get_attribute('href')
                            if href and '/status/' in href:
                                latest_tweet_url = href
                                break
                        
                        # Alternative: try to find the tweet timestamp link
                        time_links = first_tweet.find_elements(By.CSS_SELECTOR, 'time a')
                        if time_links:
                            href = time_links[0].get_attribute('href')
                            if href and '/status/' in href:
                                latest_tweet_url = href
                                break
                                
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # If we still haven't found it, try a more general approach
            if not latest_tweet_url:
                try:
                    # Look for any status links on the page
                    all_status_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
                    
                    if all_status_links:
                        # Get the first one that looks like a proper tweet URL
                        for link in all_status_links:
                            href = link.get_attribute('href')
                            if href and '/status/' in href and len(href.split('/status/')[-1]) >= 10:
                                latest_tweet_url = href
                                break
                                
                except Exception as e:
                    logger.debug(f"General status link search failed: {e}")
            
            if latest_tweet_url:
                logger.info(f"Found latest tweet URL: {latest_tweet_url}")
                return latest_tweet_url
            else:
                logger.warning(f"Could not find latest tweet URL for {twitter_url}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting latest tweet from {twitter_url}: {e}")
            return None


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

    def get_deputy_details(self, deputy_id: int) -> Dict:
        """
        Get detailed information for a specific deputy including phone and social media
        
        Args:
            deputy_id: The deputy's API ID
            
        Returns:
            Dictionary with detailed deputy information
        """
        try:
            url = f"{self.base_url}/deputados/{deputy_id}"
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            return data.get('dados', {})
        except Exception as e:
            logger.error(f"Error fetching deputy details for ID {deputy_id}: {str(e)}")
            return {}

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
    
    def extract_twitter_info(self, deputado_id: int, nome: str = None, nome_parlamentar: str = None, use_google_fallback: bool = False) -> Dict[str, any]:
        """
        Extract Twitter account and latest tweet info from deputy's profile
        
        Returns:
            Dictionary containing Twitter URL, latest tweet URL, and metadata
        """
        twitter_info = {
            'twitter_url': None,
            'latest_tweet_url': None
        }
        
        # Metadata to track source and confidence
        metadata = {
            'source': None,
            'confidence': None,
            'needs_review': False,
            'details': None
        }
        
        # STEP 1: Try to get social media from official Chamber API first
        try:
            deputy_details = self.get_deputy_details(deputado_id)
            official_social_media = deputy_details.get('redeSocial', [])
            
            if official_social_media:
                logger.info(f"Found {len(official_social_media)} official social media links for deputy {deputado_id}")
                
                # Log all URLs found in API for debugging
                for i, url_item in enumerate(official_social_media, 1):
                    logger.info(f"  API URL {i}: {url_item}")
                
                # Parse official social media URLs - look for Twitter/X only
                for url_item in official_social_media:
                    url_lower = url_item.lower()
                    
                    if 'twitter.com' in url_lower or 'x.com' in url_lower:
                        twitter_info['twitter_url'] = url_item
                        logger.info(f"Found Twitter URL in API: {url_item}")
                        break
                
                # Log if no Twitter found in API
                if not twitter_info['twitter_url']:
                    logger.info(f"No Twitter URLs found in API social media links for deputy {deputado_id}")
                
                # If found Twitter in API, set metadata and try to extract latest tweet
                if twitter_info['twitter_url']:
                    metadata['source'] = 'official_api'
                    metadata['confidence'] = 'high'
                    metadata['details'] = 'Found Twitter in official Chamber API'
                    
                    # Extract latest tweet URL
                    try:
                        twitter_searcher = TwitterSearcher()
                        latest_tweet_url = twitter_searcher.extract_latest_tweet_url(twitter_info['twitter_url'])
                        if latest_tweet_url:
                            twitter_info['latest_tweet_url'] = latest_tweet_url
                            logger.info(f"Found latest tweet URL from API: {latest_tweet_url}")
                    except Exception as e:
                        logger.error(f"Error extracting latest tweet from API source: {str(e)}")
                    
                    return {
                        'twitter_url': twitter_info['twitter_url'],
                        'latest_tweet_url': twitter_info['latest_tweet_url'],
                        'twitter_info': {'twitter_url': twitter_info['twitter_url']},
                        'metadata': metadata
                    }
                    
        except Exception as e:
            logger.warning(f"Error fetching official social media for deputy {deputado_id}: {str(e)}")
        
        # STEP 2: If API didn't provide Twitter, try Chamber website
        if not twitter_info['twitter_url']:
            logger.info(f"No Twitter found in API, trying Chamber website for deputy {deputado_id}")
            try:
                # URL of deputy's page on Chamber website
                url = f"https://www.camara.leg.br/deputados/{deputado_id}"
                logger.info(f"Scraping Chamber website: {url}")
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for Twitter widget in social media div
                social_media_div = soup.find('div', class_='l-grid-social-media')
                if social_media_div:
                    logger.info(f"Found l-grid-social-media div for deputy {deputado_id}")
                    
                    # Look for Twitter widget specifically
                    twitter_widget = social_media_div.find('div', class_=lambda x: x and 'widget-twitter' in x)
                    if twitter_widget:
                        twitter_handle = twitter_widget.get('data-urlTwitter')
                        if twitter_handle:
                            if not twitter_handle.startswith('http'):
                                twitter_url = f"https://twitter.com/{twitter_handle.lstrip('@')}"
                            else:
                                twitter_url = twitter_handle
                            
                            twitter_info['twitter_url'] = twitter_url
                            metadata['source'] = 'chamber_website'
                            metadata['confidence'] = 'high'
                            metadata['details'] = 'Found Twitter widget in Chamber website'
                
                # Also check for Twitter links in the social media div
                if not twitter_info['twitter_url'] and social_media_div:
                    twitter_links = social_media_div.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
                    for link in twitter_links:
                        href = link.get('href', '')
                        if not self._is_official_camara_link(href):
                            twitter_info['twitter_url'] = href
                            metadata['source'] = 'chamber_website'
                            metadata['confidence'] = 'medium'
                            metadata['details'] = 'Found Twitter link in Chamber website'
                            break
                
                # If no Twitter widget found, search main content for Twitter links
                if not twitter_info['twitter_url']:
                    # Search within main content, not in footer/sidebar
                    main_content = soup.find('main') or soup.find('div', class_='content') or soup.body
                    if main_content:
                        twitter_links = main_content.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
                        
                        for link in twitter_links:
                            href = link.get('href', '')
                            
                            # Skip if in footer/sidebar
                            parent_classes = []
                            parent = link.parent
                            while parent and parent.name:
                                if parent.get('class'):
                                    parent_classes.extend(parent.get('class'))
                                parent = parent.parent
                            
                            if any('footer' in cls.lower() or 'rodape' in cls.lower() for cls in parent_classes):
                                continue
                            
                            if not self._is_official_camara_link(href):
                                twitter_info['twitter_url'] = href
                                metadata['source'] = 'chamber_website'
                                metadata['confidence'] = 'medium'
                                metadata['details'] = 'Found Twitter link in Chamber website main content'
                                break
                
                # Fallback: search entire page for Twitter links
                if not twitter_info['twitter_url']:
                    all_links = soup.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
                    
                    for link in all_links:
                        href = link.get('href', '')
                        if not self._is_official_camara_link(href):
                            twitter_info['twitter_url'] = href
                            metadata['source'] = 'chamber_website'
                            metadata['confidence'] = 'low'
                            metadata['details'] = 'Found Twitter link in Chamber website fallback search'
                            break
            
                # If Twitter found on Chamber website, extract latest tweet
                if twitter_info['twitter_url']:
                    try:
                        twitter_searcher = TwitterSearcher()
                        latest_tweet_url = twitter_searcher.extract_latest_tweet_url(twitter_info['twitter_url'])
                        if latest_tweet_url:
                            twitter_info['latest_tweet_url'] = latest_tweet_url
                            logger.info(f"Found latest tweet URL from Chamber website: {latest_tweet_url}")
                    except Exception as e:
                        logger.error(f"Error extracting latest tweet from Chamber website source: {str(e)}")
                    
                    return {
                        'twitter_url': twitter_info['twitter_url'],
                        'latest_tweet_url': twitter_info['latest_tweet_url'],
                        'twitter_info': {'twitter_url': twitter_info['twitter_url']},
                        'metadata': metadata
                    }
                    
            except Exception as e:
                logger.error(f"Error extracting Twitter from Chamber website for deputy {deputado_id}: {str(e)}")
        
        # STEP 3: Google search fallback if enabled and no Twitter found
        if use_google_fallback and not twitter_info['twitter_url'] and nome and nome_parlamentar:
            logger.info(f"Attempting Google search fallback for deputy {nome_parlamentar}")
            try:
                twitter_searcher = TwitterSearcher()
                twitter_result = twitter_searcher.search_twitter_account(nome, nome_parlamentar)
                
                # Process Google Twitter result
                if twitter_result:
                    twitter_info['twitter_url'] = twitter_result['url']
                    
                    # Set metadata based on Google results
                    metadata = {
                        'source': 'google_search',
                        'confidence': twitter_result['confidence'],
                        'needs_review': twitter_result['needs_review'],
                        'details': f"Google search found Twitter: {twitter_result['score_details']}",
                    }
                    
                    # Extract latest tweet URL if Twitter was found
                    try:
                        latest_tweet_url = twitter_searcher.extract_latest_tweet_url(twitter_result['url'])
                        if latest_tweet_url:
                            twitter_info['latest_tweet_url'] = latest_tweet_url
                            logger.info(f"Found latest tweet URL from Google search: {latest_tweet_url}")
                    except Exception as tweet_e:
                        logger.error(f"Error extracting latest tweet from Google result: {str(tweet_e)}")
                    
                    # Log search results
                    logger.info(f"Google search found Twitter for {nome_parlamentar}: {twitter_result['url']}")
                    logger.info(f"Confidence: {twitter_result['confidence']}, needs review: {twitter_result['needs_review']}")
            
            except Exception as e:
                logger.error(f"Google search fallback failed for {nome_parlamentar}: {str(e)}")
        
        # Return final result
        return {
            'twitter_url': twitter_info['twitter_url'],
            'latest_tweet_url': twitter_info['latest_tweet_url'],
            'twitter_info': {'twitter_url': twitter_info['twitter_url']} if twitter_info['twitter_url'] else {},
            'metadata': metadata
        }
    
    def extract_deputies(self, update_existing: bool = True, extract_social_media: bool = True, use_google_fallback: bool = False, twitter_only: bool = False, limit: int = None):
        """
        Extract deputies data and save to database
        
        Args:
            update_existing: Update existing deputies with new data
            extract_social_media: Extract social media links (slower but more complete)
            use_google_fallback: Use Google search as fallback when no social media found on Chamber website
            twitter_only: Search only for Twitter/X links (much faster, skips Instagram and Facebook)
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
                    
                    # Get detailed deputy information (including phone number)
                    deputy_details = self.get_deputy_details(api_id)
                    phone = None
                    if deputy_details:
                        office_info = deputy_details.get('ultimoStatus', {}).get('gabinete', {})
                        phone = office_info.get('telefone')
                    
                    # Extract social media if requested
                    social_media = {}
                    metadata = {}
                    if extract_social_media:
                        nome = deputy_data.get('nome', '')
                        nome_parlamentar = deputy_data.get('nome', '')  # Use same as full name for now
                        logger.info(f"Extracting Twitter info for {nome_parlamentar}...")
                        extraction_result = self.extract_twitter_info(
                            api_id, 
                            nome=nome, 
                            nome_parlamentar=nome_parlamentar, 
                            use_google_fallback=use_google_fallback
                        )
                        twitter_info = extraction_result.get('twitter_info', {})
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
                            'telefone': phone,  # Add phone number from detailed API
                            'foto_url': deputy_data.get('urlFoto'),
                            'twitter_url': extraction_result.get('twitter_url'),
                            'latest_tweet_url': extraction_result.get('latest_tweet_url'),
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
                        
                        # Update phone number from detailed API
                        if phone is not None:
                            deputy.telefone = phone
                        
                        if deputy_data.get('urlFoto'):
                            deputy.foto_url = deputy_data['urlFoto']
                        
                        # Update Twitter info if extracted
                        if extract_social_media:
                            deputy.twitter_url = extraction_result.get('twitter_url')
                            deputy.latest_tweet_url = extraction_result.get('latest_tweet_url')
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
