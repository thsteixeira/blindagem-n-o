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
from .deputados_extractor import TwitterSearcher

logger = logging.getLogger(__name__)


class SenadoresDataExtractor:
    """
    Extractor for Brazilian Senate data using the official Senate API
    """
    
    def __init__(self):
        self.base_url = "https://legis.senado.leg.br/dadosabertos"
        self.session = requests.Session()
        # Add headers to mimic browser requests
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
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
        Parse basic senator information from XML element
        
        Args:
            senator_xml: XML element containing senator data
            
        Returns:
            Dictionary with basic senator information
        """
        try:
            # Extract identification data
            ident = senator_xml.find('IdentificacaoParlamentar')
            if ident is None:
                return None
            
            # Basic information
            codigo = self._get_xml_text(ident, 'CodigoParlamentar')
            nome_parlamentar = self._get_xml_text(ident, 'NomeParlamentar')
            nome_completo = self._get_xml_text(ident, 'NomeCompletoParlamentar')
            sexo = self._get_xml_text(ident, 'SexoParlamentar')
            email = self._get_xml_text(ident, 'EmailParlamentar')
            foto_url = self._get_xml_text(ident, 'UrlFotoParlamentar')
            pagina_url = self._get_xml_text(ident, 'UrlPaginaParlamentar')
            partido = self._get_xml_text(ident, 'SiglaPartidoParlamentar')
            uf = self._get_xml_text(ident, 'UfParlamentar')
            forma_tratamento = self._get_xml_text(ident, 'FormaTratamento')
            codigo_publico = self._get_xml_text(ident, 'CodigoPublicoNaLegAtual')
            
            # Phone information
            telefones = []
            telefones_xml = senator_xml.find('.//Telefones')
            if telefones_xml is not None:
                for tel in telefones_xml.findall('Telefone'):
                    numero = self._get_xml_text(tel, 'NumeroTelefone')
                    if numero:
                        telefones.append(numero)
            
            # Block information
            bloco = senator_xml.find('IdentificacaoParlamentar/Bloco')
            nome_bloco = None
            nome_apelido_bloco = None
            if bloco is not None:
                nome_bloco = self._get_xml_text(bloco, 'NomeBloco')
                nome_apelido_bloco = self._get_xml_text(bloco, 'NomeApelido')
            
            # Membership information
            membro_mesa = self._get_xml_text(ident, 'MembroMesa') == 'Sim'
            membro_lideranca = self._get_xml_text(ident, 'MembroLideranca') == 'Sim'
            
            return {
                'codigo': codigo,
                'nome_parlamentar': nome_parlamentar,
                'nome_completo_parlamentar': nome_completo,
                'sexo': sexo,
                'email': email,
                'telefones': telefones,
                'foto_url': foto_url,
                'pagina_parlamentar_url': pagina_url,
                'partido': partido,
                'uf': uf,
                'forma_tratamento': forma_tratamento,
                'codigo_publico_na_leg_atual': codigo_publico,
                'nome_bloco': nome_bloco,
                'nome_apelido_bloco': nome_apelido_bloco,
                'membro_mesa': membro_mesa,
                'membro_lideranca': membro_lideranca,
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar XML básico do senador: {e}")
            return None
    
    def _parse_detailed_senator_xml(self, parlamentar_xml) -> Optional[Dict]:
        """
        Parse detailed senator information from XML element
        
        Args:
            parlamentar_xml: XML element containing detailed senator data
            
        Returns:
            Dictionary with detailed senator information
        """
        try:
            # Start with basic information
            basic_data = self._parse_basic_senator_xml(parlamentar_xml)
            if not basic_data:
                return None
            
            # Add detailed information
            dados_basicos = parlamentar_xml.find('DadosBasicosParlamentar')
            if dados_basicos is not None:
                data_nascimento_str = self._get_xml_text(dados_basicos, 'DataNascimento')
                if data_nascimento_str:
                    basic_data['data_nascimento'] = parse_date(data_nascimento_str)
                
                basic_data['naturalidade'] = self._get_xml_text(dados_basicos, 'Naturalidade')
                basic_data['uf_naturalidade'] = self._get_xml_text(dados_basicos, 'UfNaturalidade')
                basic_data['endereco_parlamentar'] = self._get_xml_text(dados_basicos, 'EnderecoParlamentar')
            
            # Parse mandate information
            mandato_xml = parlamentar_xml.find('Mandato')
            if mandato_xml is not None:
                basic_data['mandato_info'] = self._parse_mandate_xml(mandato_xml)
            
            return basic_data
            
        except Exception as e:
            logger.error(f"Erro ao processar XML detalhado do senador: {e}")
            return None
    
    def _parse_mandate_xml(self, mandato_xml) -> Dict:
        """
        Parse mandate information from XML element
        
        Args:
            mandato_xml: XML element containing mandate data
            
        Returns:
            Dictionary with mandate information
        """
        mandate_data = {
            'codigo_mandato': self._get_xml_text(mandato_xml, 'CodigoMandato'),
            'uf_mandato': self._get_xml_text(mandato_xml, 'UfParlamentar'),
            'descricao_participacao': self._get_xml_text(mandato_xml, 'DescricaoParticipacao'),
        }
        
        # First legislature
        primeira_leg = mandato_xml.find('PrimeiraLegislaturaDoMandato')
        if primeira_leg is not None:
            mandate_data['primeira_legislatura_numero'] = self._get_xml_text(primeira_leg, 'NumeroLegislatura')
            
            data_inicio_str = self._get_xml_text(primeira_leg, 'DataInicio')
            if data_inicio_str:
                mandate_data['primeira_legislatura_inicio'] = parse_date(data_inicio_str)
            
            data_fim_str = self._get_xml_text(primeira_leg, 'DataFim')
            if data_fim_str:
                mandate_data['primeira_legislatura_fim'] = parse_date(data_fim_str)
        
        # Second legislature
        segunda_leg = mandato_xml.find('SegundaLegislaturaDoMandato')
        if segunda_leg is not None:
            mandate_data['segunda_legislatura_numero'] = self._get_xml_text(segunda_leg, 'NumeroLegislatura')
            
            data_inicio_str = self._get_xml_text(segunda_leg, 'DataInicio')
            if data_inicio_str:
                mandate_data['segunda_legislatura_inicio'] = parse_date(data_inicio_str)
            
            data_fim_str = self._get_xml_text(segunda_leg, 'DataFim')
            if data_fim_str:
                mandate_data['segunda_legislatura_fim'] = parse_date(data_fim_str)
        
        # Parse alternates
        suplentes = []
        suplentes_xml = mandato_xml.find('Suplentes')
        if suplentes_xml is not None:
            for suplente in suplentes_xml.findall('Suplente'):
                suplente_data = {
                    'codigo_parlamentar': self._get_xml_text(suplente, 'CodigoParlamentar'),
                    'nome_parlamentar': self._get_xml_text(suplente, 'NomeParlamentar'),
                    'descricao_participacao': self._get_xml_text(suplente, 'DescricaoParticipacao'),
                }
                suplentes.append(suplente_data)
        
        mandate_data['suplentes'] = suplentes
        return mandate_data
    
    def extract_twitter_info(self, senator_data: Dict, use_google_fallback: bool = False) -> Dict[str, Any]:
        """
        Extract Twitter account and latest tweet info for a senator
        
        First tries the official Senate API, then falls back to Google search
        if enabled.
        
        Args:
            senator_data: Dictionary containing senator information
            use_google_fallback: Use Google search to find Twitter account
            
        Returns:
            Dictionary with Twitter URL, latest tweet URL, and confidence information
        """
        senator_id = senator_data.get('codigo')
        nome_parlamentar = senator_data.get('nome_parlamentar', '')
        nome_completo = senator_data.get('nome_completo_parlamentar', nome_parlamentar)
        
        # Initialize with empty Twitter info
        social_media = {
            'twitter': None
        }
        
        # Initialize confidence metadata
        confidence_info = {
            'source': None,
            'confidence': None,
            'needs_review': False
        }
        
        # STEP 1: Try to get social media from official Senate API first
        try:
            senator_details = self.get_senator_details(senator_id)
            if senator_details:
                # Check if there are social media links in the API response
                # Look for any fields that might contain social media URLs
                potential_social_fields = []
                
                # Check common social media field names
                for field in ['redeSocial', 'redes_sociais', 'social_media', 'twitter_url', 'pagina_parlamentar_url']:
                    if field in senator_details and senator_details[field]:
                        potential_social_fields.append((field, senator_details[field]))
                
                # If we have a pagina_parlamentar_url, it might contain social media info
                if senator_details.get('pagina_parlamentar_url'):
                    logger.info(f"Found official page URL for senator {senator_id}: {senator_details['pagina_parlamentar_url']}")
                
                # Parse any social media URLs found
                for field_name, field_value in potential_social_fields:
                    if isinstance(field_value, list):
                        # Handle list of URLs (like deputies redeSocial)
                        for url_item in field_value:
                            url_lower = str(url_item).lower()
                            if 'twitter.com' in url_lower or 'x.com' in url_lower:
                                social_media['twitter'] = url_item
                                break
                    elif isinstance(field_value, str):
                        # Handle single URL string
                        url_lower = field_value.lower()
                        if 'twitter.com' in url_lower or 'x.com' in url_lower:
                            social_media['twitter'] = field_value
                
                # If found Twitter in API, set metadata and try to extract latest tweet
                if social_media['twitter']:
                    confidence_info = {
                        'source': 'official_api',
                        'confidence': 'high',
                        'needs_review': False
                    }
                    
                    logger.info(f"Found Twitter in Senate API for senator {senator_id}: {social_media['twitter']}")
                    
                    # Extract latest tweet URL
                    try:
                        twitter_searcher = TwitterSearcher()
                        latest_tweet_url = twitter_searcher.extract_latest_tweet_url(social_media['twitter'])
                        if latest_tweet_url:
                            logger.info(f"Found latest tweet URL from API for {nome_parlamentar}: {latest_tweet_url}")
                        
                        # Return early with API result
                        result = dict(social_media)
                        result['_confidence_info'] = confidence_info
                        if latest_tweet_url:
                            result['latest_tweet_url'] = latest_tweet_url
                        return result
                        
                    except Exception as tweet_e:
                        logger.error(f"Error extracting latest tweet from API for {nome_parlamentar}: {str(tweet_e)}")
                        
                        # Still return the Twitter URL even if tweet extraction fails
                        result = dict(social_media)
                        result['_confidence_info'] = confidence_info
                        return result
                        
        except Exception as e:
            logger.warning(f"Error fetching official social media for senator {senator_id}: {str(e)}")
        
        # STEP 2: Google search fallback if enabled and no Twitter found in API
        
        # STEP 2: Google search fallback if enabled and no Twitter found in API
        if use_google_fallback and not social_media['twitter'] and nome_parlamentar:
            logger.info(f"Usando Google search para encontrar redes sociais do senador {nome_parlamentar}")
            
            try:
                # Initialize Google searcher
                twitter_searcher = TwitterSearcher()
                
                # Search for senator's Twitter account
                twitter_result = twitter_searcher.search_twitter_account(
                    nome_completo, nome_parlamentar
                )
                
                # Process Twitter search result
                if twitter_result:
                    social_media['twitter'] = twitter_result['url']
                    
                    confidence_info = {
                        'source': 'google_search',
                        'confidence': twitter_result['confidence'],
                        'needs_review': twitter_result['needs_review']
                    }
                    
                    logger.info(f"Google found Twitter for {nome_parlamentar}: {twitter_result['url']} (confidence: {twitter_result['confidence']})")
                    
                    # Extract latest tweet URL if Twitter was found
                    latest_tweet_url = None
                    try:
                        logger.info(f"Extracting latest tweet URL for {nome_parlamentar} from {social_media['twitter']}")
                        latest_tweet_url = twitter_searcher.extract_latest_tweet_url(social_media['twitter'])
                        if latest_tweet_url:
                            logger.info(f"Found latest tweet URL for {nome_parlamentar}: {latest_tweet_url}")
                        else:
                            logger.warning(f"Could not extract latest tweet URL for {nome_parlamentar}")
                    except Exception as tweet_e:
                        logger.error(f"Error extracting latest tweet for {nome_parlamentar}: {str(tweet_e)}")
                    
                    # Add latest tweet URL to result
                    result = dict(social_media)
                    result['_confidence_info'] = confidence_info
                    if latest_tweet_url:
                        result['latest_tweet_url'] = latest_tweet_url
                    return result
                    
                else:
                    logger.info(f"Google search: No Twitter found for {nome_parlamentar}")
                
            except Exception as e:
                logger.error(f"Erro no Google search para senador {nome_parlamentar}: {str(e)}")
        
        # Return both social media URLs and confidence metadata
        result = dict(social_media)
        result['_confidence_info'] = confidence_info
        return result
    
    def save_senator_data(self, senator_data: Dict, social_media: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        Save simplified senator data to the database including social media and confidence info
        
        Args:
            senator_data: Dictionary containing basic senator information
            social_media: Dictionary containing social media URLs and confidence info
            
        Returns:
            Tuple of (action, message) where action is 'created', 'updated', or 'error'
        """
        if not senator_data.get('codigo'):
            return 'error', "ID do senador é obrigatório"
        
        try:
            with transaction.atomic():
                # Extract confidence information if provided
                confidence_info = {}
                if social_media and '_confidence_info' in social_media:
                    confidence_info = social_media.pop('_confidence_info')
                    
                # Prepare senator data
                senator_defaults = {
                    'nome_parlamentar': senator_data.get('nome_parlamentar', ''),
                    'partido': senator_data.get('partido', ''),
                    'uf': senator_data.get('uf', ''),
                    'email': senator_data.get('email'),
                    'telefone': ', '.join(senator_data.get('telefones', [])) if senator_data.get('telefones') else None,
                    'foto_url': senator_data.get('foto_url'),
                    'is_active': True
                }
                
                # Add Twitter info if provided
                if social_media:
                    senator_defaults.update({
                        'twitter_url': social_media.get('twitter'),
                        'latest_tweet_url': social_media.get('latest_tweet_url'),
                    })
                    
                    # Add confidence tracking fields
                    if confidence_info:
                        senator_defaults.update({
                            'social_media_source': confidence_info.get('source'),
                            'social_media_confidence': confidence_info.get('confidence'),
                            'needs_social_media_review': confidence_info.get('needs_review', False)
                        })
                
                # Create or update senator with simplified fields
                senator, created = Senador.objects.update_or_create(
                    api_id=int(senator_data['codigo']),
                    defaults=senator_defaults
                )
                
                action = "created" if created else "updated"
                action_pt = "Criado" if created else "Atualizado"
                
                # Log confidence information if available
                if confidence_info:
                    conf_source = confidence_info.get('source', 'unknown')
                    conf_level = confidence_info.get('confidence', 'none')
                    needs_review = confidence_info.get('needs_review', False)
                    
                    logger.info(f"{action_pt} senador: {senator_data.get('nome_parlamentar')} (fonte: {conf_source}, confiança: {conf_level}, revisar: {needs_review})")
                else:
                    logger.info(f"{action_pt} senador: {senator_data.get('nome_parlamentar')}")
                    
                return action, f"{action_pt} senador: {senator_data.get('nome_parlamentar')}"
                
        except Exception as e:
            logger.error(f"Erro ao salvar senador {senator_data.get('nome_parlamentar', 'N/A')}: {e}")
            return 'error', f"Erro ao salvar senador: {str(e)}"
    
    def _get_xml_text(self, parent, tag_name: str) -> Optional[str]:
        """
        Safely get text content from XML element
        
        Args:
            parent: Parent XML element
            tag_name: Name of the child tag to extract text from
            
        Returns:
            Text content or None if not found/empty
        """
        element = parent.find(tag_name) if parent is not None else None
        if element is not None and element.text:
            return element.text.strip()
        return None
    
    def extract_all_senators(self, limit: Optional[int] = None, extract_social_media: bool = False, use_google_fallback: bool = False, twitter_only: bool = False) -> Tuple[int, int]:
        """
        Extract and save all current senators with essential information and optional social media
        
        Args:
            limit: Maximum number of senators to process (for testing)
            extract_social_media: Whether to extract social media links
            use_google_fallback: Use Google search as fallback when no social media found on Senate pages
            
        Returns:
            Tuple of (created_count, updated_count)
        """
        logger.info("Iniciando extração de dados dos senadores...")
        
        # Mark all senators as inactive initially
        with transaction.atomic():
            Senador.objects.all().update(is_active=False)
            logger.info("Marcados todos os senadores como inativos")
        
        # Get list of all senators
        senators_list = self.get_current_senators_list()
        if not senators_list:
            logger.error("Nenhum senador encontrado na lista")
            return 0, 0
        
        if limit:
            senators_list = senators_list[:limit]
            logger.info(f"Processando apenas os primeiros {limit} senadores")
        
        created_count = 0
        updated_count = 0
        
        for i, senator_data in enumerate(senators_list, 1):
            nome = senator_data.get('nome_parlamentar', 'N/A')
            codigo = senator_data.get('codigo', 'N/A')
            
            logger.info(f"Processando {nome} (ID: {codigo}) [{i}/{len(senators_list)}]...")
            
            try:
                # Extract social media if requested
                social_media = None
                if extract_social_media:
                    logger.info(f"Extraindo redes sociais para {nome}...")
                    social_media = self.extract_twitter_info(
                        senator_data, 
                        use_google_fallback=use_google_fallback
                    )
                    # Reduced delay to avoid overwhelming Google (faster processing)
                    if use_google_fallback:
                        import time
                        time.sleep(0.8)
                
                # Save senator data with social media
                success, message = self.save_senator_data(senator_data, social_media)
                if success == 'created':
                    created_count += 1
                elif success == 'updated':
                    updated_count += 1
                else:
                    logger.error(f"Erro ao processar {nome}: {message}")
                    
            except Exception as e:
                logger.error(f"Erro inesperado ao processar {nome}: {e}")
        
        logger.info(f"Extração concluída! Criados: {created_count}, Atualizados: {updated_count}")
        return created_count, updated_count