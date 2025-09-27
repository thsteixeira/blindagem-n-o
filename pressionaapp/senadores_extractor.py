"""
Refactored extractor for active Brazilian senators using Grok API
New Flow:
1. Search Senate API 
2. Scrape official web page
3. If no Twitter found, use Grok API fallback
4. In all cases, search for latest tweets using Grok API
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.db import transaction
from django.utils.dateparse import parse_date

from .models import Senador
from .grok_service import GrokTwitterService, GrokAPIError
import re
import time

logger = logging.getLogger(__name__)


class SenadoresDataExtractor:
    """
    Refactored extractor for active Brazilian senators with Grok API integration
    Follows the new 4-step flow for Twitter discovery and tweet extraction
    """
    
    def __init__(self):
        self.base_url = "https://legis.senado.leg.br/dadosabertos"
        self.session = requests.Session()
        # Add headers to mimic browser requests
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Initialize Grok service
        try:
            self.grok_service = GrokTwitterService()
            logger.info("Grok Twitter service initialized successfully for senators")
        except ValueError as e:
            logger.error(f"Failed to initialize Grok service for senators: {e}")
            self.grok_service = None
    
    def get_current_senators_list(self) -> List[Dict]:
        """
        Get list of all current senators from Senate API
        
        Returns:
            List of dictionaries containing basic senator data
        """
        url = f"{self.base_url}/senador/lista/atual"
        logger.info(f"Fetching senators list from: {url}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            senators = root.findall('.//Parlamentar')
            
            logger.info(f"Encontrados {len(senators)} senadores ativos")
            
            senators_data = []
            for senator_xml in senators:
                senator_data = self._parse_basic_senator_xml(senator_xml)
                if senator_data:
                    senators_data.append(senator_data)
            
            return senators_data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar lista de senadores: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"Erro ao parsing XML da lista de senadores: {e}")
            return []
    
    def get_senator_details(self, senator_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific senator
        
        Args:
            senator_id: The senator's ID code
            
        Returns:
            Dictionary with detailed senator information
        """
        url = f"{self.base_url}/senador/{senator_id}"
        logger.info(f"Buscando detalhes do senador {senator_id}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            parlamentar = root.find('.//Parlamentar')
            
            if parlamentar is None:
                logger.warning(f"Parlamentar não encontrado no XML para senador {senator_id}")
                return None
            
            return self._parse_detailed_senator_xml(parlamentar)
            
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar detalhes do senador {senator_id}: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"Erro ao parsing XML dos detalhes do senador {senator_id}: {e}")
            return None
    
    def _parse_basic_senator_xml(self, senator_xml) -> Optional[Dict]:
        """
        Parse basic senator data from XML element
        
        Args:
            senator_xml: XML element containing senator data
            
        Returns:
            Dictionary with parsed senator data
        """
        try:
            identificacao = senator_xml.find('IdentificacaoParlamentar')
            if identificacao is None:
                return None
            
            # Extract basic info
            codigo_parlamentar = self._get_xml_text(identificacao, 'CodigoParlamentar')
            nome_parlamentar = self._get_xml_text(identificacao, 'NomeParlamentar')
            nome_completo = self._get_xml_text(identificacao, 'NomeCompletoParlamentar')
            
            # Get party and state info
            partido = self._get_xml_text(identificacao, 'SiglaPartidoParlamentar')
            if not partido:
                partido = "S/PARTIDO"  # Default fallback to prevent NOT NULL constraint
            uf = self._get_xml_text(identificacao, 'UfParlamentar')
            
            # Get email
            email = self._get_xml_text(identificacao, 'EmailParlamentar')
            
            # Get photo URL
            foto_url = self._get_xml_text(identificacao, 'UrlFotoParlamentar')
            
            return {
                'codigo_parlamentar': codigo_parlamentar,
                'nome_parlamentar': nome_parlamentar,
                'nome_completo': nome_completo,
                'partido': partido,
                'uf': uf,
                'email': email,
                'foto_url': foto_url
            }
            
        except Exception as e:
            logger.error(f"Erro ao parsing dados básicos do senador: {e}")
            return None
    
    def _parse_detailed_senator_xml(self, parlamentar_xml) -> Dict:
        """
        Parse detailed senator data from XML element
        
        Args:
            parlamentar_xml: XML element containing detailed senator data
            
        Returns:
            Dictionary with detailed senator data
        """
        try:
            identificacao = parlamentar_xml.find('IdentificacaoParlamentar')
            
            # Basic info
            codigo_parlamentar = self._get_xml_text(identificacao, 'CodigoParlamentar')
            nome_parlamentar = self._get_xml_text(identificacao, 'NomeParlamentar')
            nome_completo = self._get_xml_text(identificacao, 'NomeCompletoParlamentar')
            uf = self._get_xml_text(identificacao, 'UfParlamentar')
            email = self._get_xml_text(identificacao, 'EmailParlamentar')
            foto_url = self._get_xml_text(identificacao, 'UrlFotoParlamentar')
            
            # Party information
            partido = self._get_xml_text(identificacao, 'SiglaPartidoParlamentar')
            if not partido:
                partido = "S/PARTIDO"  # Default fallback to prevent NOT NULL constraint
            
            # Contact information
            telefone = None
            gabinete = parlamentar_xml.find('.//Gabinete')
            if gabinete is not None:
                telefone = self._get_xml_text(gabinete, 'Telefone')
            
            # Mandate information
            mandato = parlamentar_xml.find('.//Mandato')
            data_inicio_mandato = None
            data_fim_mandato = None
            if mandato is not None:
                data_inicio_str = self._get_xml_text(mandato, 'DataInicioMandato')
                data_fim_str = self._get_xml_text(mandato, 'DataFimMandato')
                
                if data_inicio_str:
                    data_inicio_mandato = parse_date(data_inicio_str)
                if data_fim_str:
                    data_fim_mandato = parse_date(data_fim_str)
            
            return {
                'codigo_parlamentar': codigo_parlamentar,
                'nome_parlamentar': nome_parlamentar,
                'nome_completo': nome_completo,
                'partido': partido,
                'uf': uf,
                'email': email,
                'telefone': telefone,
                'foto_url': foto_url,
                'data_inicio_mandato': data_inicio_mandato,
                'data_fim_mandato': data_fim_mandato
            }
            
        except Exception as e:
            logger.error(f"Erro ao parsing dados detalhados do senador: {e}")
            return {}
    
    def _get_xml_text(self, parent, tag_name: str) -> Optional[str]:
        """
        Safely extract text content from XML element
        
        Args:
            parent: Parent XML element
            tag_name: Name of the child tag to extract
            
        Returns:
            Text content or None if not found
        """
        if parent is None:
            return None
            
        element = parent.find(tag_name)
        if element is not None and element.text:
            return element.text.strip()
        return None
    
    def _is_official_senate_link(self, url: str) -> bool:
        """
        Check if a URL is from official Senate accounts
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # List of official Senate identifiers
        official_patterns = [
            'senadofederal',
            'senado.leg.br',
            'senadodobrasil',
            '@senadodobrasil',
            '@senadofederal',
            'senado.gov.br',
            'senadofederal.gov.br',
            'congressonacional',
        ]
        
        return any(pattern.lower() in url_lower for pattern in official_patterns)
    
    def extract_twitter_info(self, codigo_parlamentar: str, nome_completo: str = None, 
                           nome_parlamentar: str = None, partido: str = None, uf: str = None) -> Dict[str, any]:
        """
        Extract Twitter account and tweets using the new 4-step flow:
        1. Try Senate API (if available)
        2. Try Senate website scraping
        3. Try Grok API fallback (if no Twitter found)
        4. Use Grok API to get latest tweets (always)
        
        Returns:
            Dictionary containing Twitter URL, tweets, and metadata
        """
        result = {
            'twitter_url': None,
            'tweets_data': [],
            'metadata': {
                'source': None,
                'confidence': None,
                'needs_review': False,
                'details': None,
                'extraction_method': []
            }
        }
        
        # STEP 1: Try to get Twitter from official Senate API
        # Note: Senate API doesn't typically include social media like Chamber API
        logger.info(f"Step 1: Checking Senate API for senator {codigo_parlamentar} ({nome_parlamentar})")
        try:
            # Senate API usually doesn't have social media fields, but check detailed info
            senator_details = self.get_senator_details(codigo_parlamentar)
            # Most Senate API responses don't include social media, so this will typically be empty
            # But we keep this step for completeness and future API updates
            
        except Exception as e:
            logger.warning(f"Error in Step 1 (Senate API): {str(e)}")
        
        # STEP 2: Try Senate website scraping
        logger.info(f"Step 2: Scraping Senate website for senator {codigo_parlamentar}")
        try:
            # Senate profile URLs follow pattern: https://www25.senado.leg.br/web/senadores/senador/-/perfil/{codigo}
            url = f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{codigo_parlamentar}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for social media links in the Senate website
            # Check for Twitter links in various possible locations
            twitter_links = soup.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
            
            for link in twitter_links:
                href = link.get('href', '')
                if not self._is_official_senate_link(href):
                    result['twitter_url'] = href
                    result['metadata']['source'] = 'senate_website'
                    result['metadata']['confidence'] = 'medium'
                    result['metadata']['details'] = 'Found Twitter link in Senate website'
                    result['metadata']['extraction_method'].append('senate_website_scraping')
                    logger.info(f"✓ Found Twitter link: {result['twitter_url']}")
                    break
            
            # Also check for social media sections or specific Twitter widgets
            social_sections = soup.find_all(['div', 'section'], class_=re.compile(r'social|rede|twitter', re.I))
            for section in social_sections:
                if not result['twitter_url']:
                    twitter_links = section.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
                    for link in twitter_links:
                        href = link.get('href', '')
                        if not self._is_official_senate_link(href):
                            result['twitter_url'] = href
                            result['metadata']['source'] = 'senate_website'
                            result['metadata']['confidence'] = 'medium'
                            result['metadata']['details'] = 'Found Twitter in social media section'
                            result['metadata']['extraction_method'].append('senate_website_social')
                            logger.info(f"✓ Found Twitter in social section: {result['twitter_url']}")
                            break
                            
        except Exception as e:
            logger.warning(f"Error in Step 2 (Senate website): {str(e)}")
        
        # STEP 3: Use Grok API fallback if still no Twitter found
        if not result['twitter_url'] and self.grok_service:
            logger.info(f"Step 3: Using Grok API fallback for senator {nome_parlamentar}")
            try:
                # Build additional context for Grok search
                additional_context = []
                if partido:
                    additional_context.append(f"partido {partido}")
                if uf:
                    additional_context.append(f"estado {uf}")
                
                context_str = " ".join(additional_context) if additional_context else None
                
                grok_profile = self.grok_service.find_twitter_profile(
                    nome=nome_completo,
                    nome_parlamentar=nome_parlamentar,
                    role="senador",
                    additional_context=context_str
                )
                
                if grok_profile:
                    result['twitter_url'] = grok_profile['url']
                    result['metadata']['source'] = 'grok_api'
                    result['metadata']['confidence'] = 'medium' if grok_profile['confidence_score'] > 0.7 else 'low'
                    result['metadata']['needs_review'] = grok_profile['confidence_score'] < 0.8
                    result['metadata']['details'] = f"Grok API found profile (confidence: {grok_profile['confidence_score']})"
                    result['metadata']['extraction_method'].append('grok_fallback')
                    result['metadata']['grok_profile_data'] = grok_profile
                    logger.info(f"✓ Grok found Twitter: {result['twitter_url']} (confidence: {grok_profile['confidence_score']})")
                    
            except Exception as e:
                logger.warning(f"Error in Step 3 (Grok fallback): {str(e)}")
        
        # STEP 4: Always try to get latest tweets using Grok API (if we have a Twitter URL)
        if result['twitter_url'] and self.grok_service:
            logger.info(f"Step 4: Getting latest tweets via Grok API for {nome_parlamentar}")
            try:
                tweets = self.grok_service.get_latest_tweets(
                    twitter_url=result['twitter_url'],
                    max_tweets=5,
                    days_back=180  # 6 months
                )
                
                if tweets:
                    # Convert Grok tweet format to our expected format
                    result['tweets_data'] = []
                    for tweet in tweets:
                        tweet_data = {
                            'url': tweet.get('url'),
                            'text': tweet.get('text'),
                            'parliamentarian': nome_parlamentar,
                            'found_via': 'grok_api',
                            'created_at': tweet.get('created_at'),
                            'tweet_id': tweet.get('tweet_id'),
                            'metrics': tweet.get('metrics', {}),
                            'grok_metadata': {
                                'username': tweet.get('username'),
                                'display_name': tweet.get('display_name'),
                                'is_retweet': tweet.get('is_retweet', False),
                                'is_reply': tweet.get('is_reply', False)
                            }
                        }
                        result['tweets_data'].append(tweet_data)
                    
                    result['metadata']['extraction_method'].append('grok_tweets')
                    logger.info(f"✓ Retrieved {len(tweets)} tweets via Grok API")
                else:
                    logger.info(f"No tweets found via Grok API for {nome_parlamentar}")
                    
            except Exception as e:
                logger.warning(f"Error in Step 4 (Grok tweets): {str(e)}")
        
        # Log final result summary
        method_summary = " → ".join(result['metadata']['extraction_method'])
        logger.info(f"Extraction complete for {nome_parlamentar}: {method_summary}")
        logger.info(f"  Twitter URL: {'✓' if result['twitter_url'] else '✗'}")
        logger.info(f"  Tweets found: {len(result['tweets_data'])}")
        logger.info(f"  Source: {result['metadata']['source']}")
        logger.info(f"  Confidence: {result['metadata']['confidence']}")
        
        return result
    
    def extract_senators(self, update_existing: bool = True, limit: int = None):
        """
        Extract senators data and save to database using the new Grok-enhanced flow
        
        Args:
            update_existing: Update existing senators with new data
            limit: Limit number of senators to process (for testing)
        
        Returns:
            tuple: (created_count, updated_count)
        """
        logger.info("Starting senators data extraction with Grok API integration...")
        
        # Check if Grok service is available
        if not self.grok_service:
            logger.warning("Grok service not available - proceeding with limited functionality")
        
        senators_data = self.get_current_senators_list()
        if not senators_data:
            logger.warning("No senators data found")
            return 0, 0
        
        created_count = 0
        updated_count = 0
        
        # Apply limit if specified
        if limit:
            senators_data = senators_data[:limit]
            logger.info(f"Processing limited to {limit} senators")
        
        with transaction.atomic():
            # First, mark all senators as inactive
            Senador.objects.all().update(is_active=False)
            
            for i, senator_data in enumerate(senators_data, 1):
                try:
                    codigo_parlamentar = senator_data.get('codigo_parlamentar')
                    if not codigo_parlamentar:
                        continue
                    
                    nome_completo = senator_data.get('nome_completo', '')
                    nome_parlamentar = senator_data.get('nome_parlamentar', '')
                    partido = senator_data.get('partido', '')
                    uf = senator_data.get('uf', '')
                    
                    logger.info(f"\n[{i}/{len(senators_data)}] Processing: {nome_parlamentar} ({partido}-{uf})")
                    
                    # Get detailed senator information
                    senator_details = self.get_senator_details(codigo_parlamentar)
                    telefone = None
                    if senator_details:
                        telefone = senator_details.get('telefone')
                    
                    # Extract Twitter info using new 4-step flow
                    extraction_result = self.extract_twitter_info(
                        codigo_parlamentar=codigo_parlamentar,
                        nome_completo=nome_completo,
                        nome_parlamentar=nome_parlamentar,
                        partido=partido,
                        uf=uf
                    )
                    
                    twitter_url = extraction_result.get('twitter_url')
                    tweets_data = extraction_result.get('tweets_data', [])
                    metadata = extraction_result.get('metadata', {})
                    
                    # Get or create senator
                    senator, created = Senador.objects.get_or_create(
                        api_id=codigo_parlamentar,
                        defaults={
                            'nome_parlamentar': nome_parlamentar,
                            'partido': partido,
                            'uf': uf,
                            'email': senator_data.get('email'),
                            'telefone': telefone,
                            'foto_url': senator_data.get('foto_url'),
                            'twitter_url': twitter_url,
                            'social_media_source': metadata.get('source'),
                            'social_media_confidence': metadata.get('confidence'),
                            'needs_social_media_review': metadata.get('needs_review', False),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                        logger.info(f"✓ Created: {senator.nome_parlamentar}")
                    elif update_existing:
                        # Update existing senator
                        senator.nome_parlamentar = nome_parlamentar
                        senator.partido = partido
                        senator.uf = uf
                        senator.is_active = True
                        
                        if senator_data.get('email'):
                            senator.email = senator_data['email']
                        
                        if telefone is not None:
                            senator.telefone = telefone
                        
                        if senator_data.get('foto_url'):
                            senator.foto_url = senator_data['foto_url']
                        
                        # Update Twitter info
                        senator.twitter_url = twitter_url
                        senator.social_media_source = metadata.get('source')
                        senator.social_media_confidence = metadata.get('confidence')
                        senator.needs_social_media_review = metadata.get('needs_review', False)
                        
                        senator.save()
                        updated_count += 1
                        logger.info(f"✓ Updated: {senator.nome_parlamentar}")
                    else:
                        # Just mark as active
                        senator.is_active = True
                        senator.save()
                    
                    # Save tweets if any were found
                    if tweets_data:
                        try:
                            senator.update_tweets(tweets_data)
                            logger.info(f"✓ Saved {len(tweets_data)} tweets for {senator.nome_parlamentar}")
                        except Exception as tweet_save_e:
                            logger.error(f"✗ Error saving tweets for {senator.nome_parlamentar}: {str(tweet_save_e)}")
                    
                    # Add delay to respect API rate limits
                    if self.grok_service and i % 10 == 0:  # Every 10 requests
                        logger.info("Rate limiting pause...")
                        time.sleep(2)
                        
                except Exception as e:
                    senator_name = senator_data.get('nome_parlamentar', 'Unknown') if senator_data else 'Unknown'
                    logger.error(f"✗ Error processing senator {senator_name}: {str(e)}")
                    continue
        
        logger.info(f"\nExtraction completed: {created_count} created, {updated_count} updated")
        logger.info("New Grok-enhanced extraction flow completed successfully!")
        return created_count, updated_count