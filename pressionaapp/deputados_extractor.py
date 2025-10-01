"""
Extractor for active Brazilian deputies using Grok API for profile discovery
New Flow:
1. Search Camara dos Deputados API 
2. Scrape official web page
3. If no Twitter found, use Grok API fallback
"""

import requests
import logging
from typing import Dict, List, Optional
from django.db import transaction
from .models import Deputado
from .grok_service import GrokTwitterService, GrokAPIError
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeputadosDataExtractor:
    """
    Extractor for active Brazilian deputies with Grok API integration
    Focuses on Twitter profile discovery using 3-step flow
    """
    
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Initialize Grok service
        try:
            self.grok_service = GrokTwitterService()
            logger.info("Grok Twitter service initialized successfully")
        except ValueError as e:
            logger.error(f"Failed to initialize Grok service: {e}")
            self.grok_service = None
    
    def _clean_twitter_url(self, url: str) -> str:
        """Clean Twitter URL to standardized format without @ or www"""
        if not url:
            return url
            
        import re
        # Remove protocol, www, and extract clean username
        pattern = r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(?:@)?(\w+)(?:\?.*)?(?:#.*)?'
        match = re.match(pattern, url.strip())
        
        if match:
            username = match.group(1)
            # Return clean X.com URL format
            return f"https://x.com/{username}"
        
        # If pattern doesn't match, return original URL
        return url.strip()
        
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
        
        # List of official Chamber identifiers
        official_patterns = [
            'camaradeputados',
            'camara.leg.br',
            'camaradosdeputados',
            'UC-ZkSRh-7UEuwXJQ9UMCFJA',  # Official YouTube channel
            '/camaradeputados',
            '@camaradeputados',
            '@camaradosdeputados',
            'camaradeputados.leg.br',
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
    
    def extract_twitter_info(self, deputado_id: int, nome: str = None, nome_parlamentar: str = None, 
                           partido: str = None, uf: str = None) -> Dict[str, any]:
        """
        Extract Twitter account using the 3-step flow:
        1. Try Chamber API
        2. Try Chamber website scraping
        3. Try Grok API fallback (if no Twitter found)
        
        Returns:
            Dictionary containing Twitter URL and metadata
        """
        result = {
            'twitter_url': None,
            'metadata': {
                'source': None,
                'confidence': None,
                'needs_review': False,
                'details': None,
                'extraction_method': []
            }
        }
        
        # STEP 1: Try to get Twitter from official Chamber API
        logger.info(f"Step 1: Checking Chamber API for deputy {deputado_id} ({nome_parlamentar})")
        try:
            deputy_details = self.get_deputy_details(deputado_id)
            official_social_media = deputy_details.get('redeSocial', [])
            
            if official_social_media:
                logger.info(f"Found {len(official_social_media)} official social media links")
                
                # Look for Twitter/X only
                for url_item in official_social_media:
                    url_lower = url_item.lower()
                    
                    if 'twitter.com' in url_lower or 'x.com' in url_lower:
                        result['twitter_url'] = self._clean_twitter_url(url_item)
                        result['metadata']['source'] = 'official_api'
                        result['metadata']['confidence'] = 'high'
                        result['metadata']['details'] = 'Found Twitter in official Chamber API'
                        result['metadata']['extraction_method'].append('chamber_api')
                        logger.info(f"✓ Found Twitter in API: {url_item}")
                        break
                        
        except Exception as e:
            logger.warning(f"Error in Step 1 (Chamber API): {str(e)}")
        
        # STEP 2: Try Chamber website scraping if not found in API
        if not result['twitter_url']:
            logger.info(f"Step 2: Scraping Chamber website for deputy {deputado_id}")
            try:
                url = f"https://www.camara.leg.br/deputados/{deputado_id}"
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for Twitter widget in social media div
                social_media_div = soup.find('div', class_='l-grid-social-media')
                if social_media_div:
                    # Look for Twitter widget specifically
                    twitter_widget = social_media_div.find('div', class_=lambda x: x and 'widget-twitter' in x)
                    if twitter_widget:
                        twitter_handle = twitter_widget.get('data-urlTwitter')
                        if twitter_handle:
                            if not twitter_handle.startswith('http'):
                                result['twitter_url'] = self._clean_twitter_url(f"https://x.com/{twitter_handle.lstrip('@')}")
                            else:
                                result['twitter_url'] = self._clean_twitter_url(twitter_handle)
                            
                            result['metadata']['source'] = 'chamber_website'
                            result['metadata']['confidence'] = 'high'
                            result['metadata']['details'] = 'Found Twitter widget in Chamber website'
                            result['metadata']['extraction_method'].append('chamber_website_widget')
                            logger.info(f"✓ Found Twitter widget: {result['twitter_url']}")
                
                # Also check for Twitter links if widget not found
                if not result['twitter_url'] and social_media_div:
                    twitter_links = social_media_div.find_all('a', href=re.compile(r'(twitter\.com|x\.com)'))
                    for link in twitter_links:
                        href = link.get('href', '')
                        if not self._is_official_camara_link(href):
                            result['twitter_url'] = self._clean_twitter_url(href)
                            result['metadata']['source'] = 'chamber_website'
                            result['metadata']['confidence'] = 'medium'
                            result['metadata']['details'] = 'Found Twitter link in Chamber website'
                            result['metadata']['extraction_method'].append('chamber_website_scraping')
                            logger.info(f"✓ Found Twitter link: {result['twitter_url']}")
                            break
                            
            except Exception as e:
                logger.warning(f"Error in Step 2 (Chamber website): {str(e)}")
        
        # STEP 3: Use Grok API fallback if still no Twitter found
        if not result['twitter_url'] and self.grok_service:
            logger.info(f"Step 3: Using Grok API fallback for deputy {nome_parlamentar}")
            try:
                # Build additional context for Grok search
                additional_context = []
                if partido:
                    additional_context.append(f"partido {partido}")
                if uf:
                    additional_context.append(f"estado {uf}")
                
                context_str = " ".join(additional_context) if additional_context else None
                
                grok_profile = self.grok_service.find_twitter_profile(
                    nome=nome,
                    nome_parlamentar=nome_parlamentar,
                    role="deputado",
                    additional_context=context_str
                )
                
                if grok_profile:
                    result['twitter_url'] = self._clean_twitter_url(grok_profile['url'])
                    result['metadata']['source'] = 'grok_api'
                    result['metadata']['confidence'] = 'medium' if grok_profile['confidence_score'] > 0.7 else 'low'
                    result['metadata']['needs_review'] = grok_profile['confidence_score'] < 0.8
                    result['metadata']['details'] = f"Grok API found profile (confidence: {grok_profile['confidence_score']})"
                    result['metadata']['extraction_method'].append('grok_fallback')
                    result['metadata']['grok_profile_data'] = grok_profile
                    logger.info(f"✓ Grok found Twitter: {result['twitter_url']} (confidence: {grok_profile['confidence_score']})")
                    
            except Exception as e:
                logger.warning(f"Error in Step 3 (Grok fallback): {str(e)}")
        

        
        # Log final result summary
        method_summary = " → ".join(result['metadata']['extraction_method'])
        logger.info(f"Profile extraction complete for {nome_parlamentar}: {method_summary}")
        logger.info(f"  Twitter URL: {'✓' if result['twitter_url'] else '✗'}")
        logger.info(f"  Source: {result['metadata']['source']}")
        logger.info(f"  Confidence: {result['metadata']['confidence']}")
        
        return result
    
    def extract_deputies(self, update_existing: bool = True, limit: int = None, skip_existing: bool = False):
        """
        Extract deputies data and save to database using the new Grok-enhanced flow
        
        Args:
            update_existing: Update existing deputies with new data
            limit: Limit number of deputies to process (for testing)
            skip_existing: Skip deputies that already exist in database
        
        Returns:
            tuple: (created_count, updated_count)
        """
        logger.info("Starting deputies data extraction with Grok API integration...")
        
        # Check if Grok service is available
        if not self.grok_service:
            logger.warning("Grok service not available - proceeding with limited functionality")
        
        deputies_data = self.get_current_deputies()
        if not deputies_data:
            logger.warning("No deputies data found")
            return 0, 0
        
        # Get existing deputy API IDs if skip_existing is True
        existing_api_ids = set()
        if skip_existing:
            from .models import Deputado
            existing_api_ids = set(Deputado.objects.values_list('api_id', flat=True))
            logger.info(f"Found {len(existing_api_ids)} existing deputies in database - will skip them")
        
        # Filter out existing deputies if requested
        # NOTE: Even when skipping existing deputies, we still need to manage their active/inactive status
        # in the transaction below to ensure database consistency with the current API state
        if skip_existing and existing_api_ids:
            original_count = len(deputies_data)
            deputies_data = [d for d in deputies_data if d.get('id') not in existing_api_ids]
            filtered_count = original_count - len(deputies_data)
            logger.info(f"Filtered out {filtered_count} existing deputies. Processing {len(deputies_data)} new deputies.")
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Apply limit if specified
        if limit:
            deputies_data = deputies_data[:limit]
            logger.info(f"Processing limited to {limit} deputies")
        
        with transaction.atomic():
            # First, mark all deputies as inactive
            Deputado.objects.all().update(is_active=False)
            
            # If skip_existing is enabled, we still need to mark existing deputies as active
            # if they appear in the current API response (they're still serving)
            if skip_existing and existing_api_ids:
                # Get all API IDs from the OFFICIAL current deputies API (not legislature filtered)
                # This ensures we sync with the same data source as the sync_deputy_status command
                try:
                    response = self.session.get(f"{self.base_url}/deputados")
                    response.raise_for_status()
                    official_data = response.json()
                    all_current_api_ids = [d.get('id') for d in official_data.get('dados', []) if d.get('id')]
                except Exception as e:
                    logger.warning(f"Could not fetch official current deputies for sync: {e}")
                    # Fallback to the filtered data we already have
                    all_current_api_ids = [d.get('id') for d in self.get_current_deputies() if d.get('id')]
                
                # Mark existing deputies as active if they're still in the current API
                existing_active_ids = set(all_current_api_ids).intersection(existing_api_ids)
                if existing_active_ids:
                    Deputado.objects.filter(api_id__in=existing_active_ids).update(is_active=True)
                    logger.info(f"Marked {len(existing_active_ids)} existing deputies as active (still serving)")
                else:
                    logger.info(f"No existing deputies found in current API response")
            
            for i, deputy_data in enumerate(deputies_data, 1):
                try:
                    api_id = deputy_data.get('id')
                    if not api_id:
                        continue
                    
                    nome_parlamentar = deputy_data.get('nome', '')  # Parliamentary name
                    partido = deputy_data.get('siglaPartido', '')
                    uf = deputy_data.get('siglaUf', '')
                    
                    logger.info(f"\n[{i}/{len(deputies_data)}] Processing: {nome_parlamentar} ({partido}-{uf})")
                    
                    # Get detailed deputy information (including real name)
                    deputy_details = self.get_deputy_details(api_id)
                    nome = nome_parlamentar  # Default fallback
                    if deputy_details:
                        # Use the full civil name for more accurate Grok searches
                        nome_civil = deputy_details.get('nomeCivil', '')
                        if nome_civil:
                            nome = nome_civil.title()  # Convert to title case for better readability
                    phone = None
                    if deputy_details:
                        office_info = deputy_details.get('ultimoStatus', {}).get('gabinete', {})
                        phone = office_info.get('telefone')
                    
                    # Extract Twitter info using new 4-step flow
                    extraction_result = self.extract_twitter_info(
                        deputado_id=api_id,
                        nome=nome,
                        nome_parlamentar=nome_parlamentar,
                        partido=partido,
                        uf=uf
                    )
                    
                    twitter_url = extraction_result.get('twitter_url')
                    metadata = extraction_result.get('metadata', {})
                    
                    # Get or create deputy
                    deputy, created = Deputado.objects.get_or_create(
                        api_id=api_id,
                        defaults={
                            'nome_parlamentar': nome_parlamentar,
                            'partido': partido,
                            'uf': uf,
                            'email': deputy_data.get('email'),
                            'telefone': phone,
                            'foto_url': deputy_data.get('urlFoto'),
                            'twitter_url': twitter_url,
                            'social_media_source': metadata.get('source'),
                            'social_media_confidence': metadata.get('confidence'),
                            'needs_social_media_review': metadata.get('needs_review', False),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                        logger.info(f"✓ Created: {deputy.nome_parlamentar}")
                    elif update_existing:
                        # Update existing deputy
                        deputy.nome_parlamentar = nome_parlamentar
                        deputy.partido = partido
                        deputy.uf = uf
                        deputy.is_active = True
                        
                        if deputy_data.get('email'):
                            deputy.email = deputy_data['email']
                        
                        if phone is not None:
                            deputy.telefone = phone
                        
                        if deputy_data.get('urlFoto'):
                            deputy.foto_url = deputy_data['urlFoto']
                        
                        # Update Twitter info
                        deputy.twitter_url = twitter_url
                        deputy.social_media_source = metadata.get('source')
                        deputy.social_media_confidence = metadata.get('confidence')
                        deputy.needs_social_media_review = metadata.get('needs_review', False)
                        
                        deputy.save()
                        updated_count += 1
                        logger.info(f"✓ Updated: {deputy.nome_parlamentar}")
                    else:
                        # Just mark as active (deputy exists but not updating)
                        deputy.is_active = True
                        deputy.save()
                        skipped_count += 1
                        logger.info(f"✓ Skipped (already exists): {deputy.nome_parlamentar}")
                    

                    
                    # Add delay to respect API rate limits
                    if self.grok_service and i % 10 == 0:  # Every 10 requests
                        logger.info("Rate limiting pause...")
                        time.sleep(2)
                        
                except Exception as e:
                    deputy_name = deputy_data.get('nome', 'Unknown') if deputy_data else 'Unknown'
                    logger.error(f"✗ Error processing deputy {deputy_name}: {str(e)}")
                    continue
        
        if skip_existing:
            logger.info(f"\nExtraction completed: {created_count} created, {updated_count} updated, {skipped_count} skipped (already existed)")
        else:
            logger.info(f"\nExtraction completed: {created_count} created, {updated_count} updated")
        logger.info("New Grok-enhanced extraction flow completed successfully!")
        return created_count, updated_count