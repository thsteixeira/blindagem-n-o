"""
Extrator de dados dos deputados da Câmara dos Deputados
Combina API oficial da Câmara com web scraping para redes sociais
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from django.utils import timezone
from .models import Deputado, HistoricoMandato
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeputadosDataExtractor:
    """
    Extrator híbrido para dados dos deputados brasileiros:
    - Usa API oficial da Câmara para dados estruturados
    - Usa web scraping para extrair redes sociais
    """
    
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def get_legislaturas(self) -> List[Dict]:
        """
        Obtém todas as legislaturas disponíveis
        """
        try:
            url = f"{self.base_url}/legislaturas"
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            return data.get('dados', [])
        except Exception as e:
            logger.error(f"Erro ao obter legislaturas: {str(e)}")
            return []
    
    def get_deputados_by_legislatura(self, legislatura_id: int) -> List[Dict]:
        """
        Obtém todos os deputados de uma legislatura específica
        """
        try:
            url = f"{self.base_url}/deputados"
            params = {
                'idLegislatura': legislatura_id,
                'ordem': 'ASC',
                'ordenarPor': 'nome'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('dados', [])
        except Exception as e:
            logger.error(f"Erro ao obter deputados da legislatura {legislatura_id}: {str(e)}")
            return []
    
    def get_deputado_detalhes(self, deputado_id: int) -> Optional[Dict]:
        """
        Obtém detalhes completos de um deputado específico
        """
        try:
            url = f"{self.base_url}/deputados/{deputado_id}"
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            return data.get('dados', {})
        except Exception as e:
            logger.error(f"Erro ao obter detalhes do deputado {deputado_id}: {str(e)}")
            return None
    
    def get_deputado_mandatos(self, deputado_id: int) -> List[Dict]:
        """
        Obtém histórico de mandatos de um deputado
        """
        try:
            # Tentar primeiro endpoint
            url = f"{self.base_url}/deputados/{deputado_id}/mandatos"
            response = self.session.get(url)
            
            if response.status_code == 405:
                # Tentar endpoint alternativo
                url = f"{self.base_url}/deputados/{deputado_id}"
                response = self.session.get(url)
                response.raise_for_status()
                
                # Extrair informação do mandato atual dos detalhes
                data = response.json()
                deputado_info = data.get('dados', {})
                ultimo_status = deputado_info.get('ultimoStatus', {})
                
                if ultimo_status:
                    return [{
                        'idLegislatura': ultimo_status.get('idLegislatura'),
                        'dataInicio': '2023-02-01',  # Data padrão início 57ª legislatura
                        'dataFim': None,
                        'situacao': ultimo_status.get('situacaoNaLegislatura', 'TITULAR EM EXERCICIO'),
                        'condicaoEleitoral': 'ELEITO'
                    }]
                return []
            
            response.raise_for_status()
            data = response.json()
            return data.get('dados', [])
        except Exception as e:
            logger.error(f"Erro ao obter mandatos do deputado {deputado_id}: {str(e)}")
            return []
    
    def _is_official_camara_link(self, url: str) -> bool:
        """
        Verifica se um link é da conta oficial da Câmara dos Deputados
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # Lista de identificadores oficiais da Câmara
        official_patterns = [
            'camaradeputados',
            'camara.leg.br',
            'camaradosdeputados',
            'UC-ZkSRh-7UEuwXJQ9UMCFJA',  # Canal oficial YouTube
            '/camaradeputados',
            '@camaradeputados',
            '@camaradosdeputados'
        ]
        
        return any(pattern.lower() in url_lower for pattern in official_patterns)
    
    def extract_social_media_links(self, deputado_id: int) -> Dict[str, str]:
        """
        Extrai links de redes sociais da página do deputado
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
            # URL da página do deputado no site da Câmara
            url = f"https://www.camara.leg.br/deputados/{deputado_id}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procurar especificamente por links de Instagram com classe "username-insta"
            instagram_link = soup.find('a', class_='username-insta')
            if instagram_link and instagram_link.get('href'):
                instagram_url = instagram_link.get('href')
                if 'camaradeputados' not in instagram_url.lower():
                    social_media['instagram'] = instagram_url
                else:
                    pass  # Instagram oficial ignorado
            
            # Se não encontrou Instagram com classe específica, tentar outras estratégias
            if not social_media['instagram']:
                # Procurar pela seção que contém Instagram específico do deputado
                instagram_heading = soup.find('h3', string='INSTAGRAM') or soup.find('h4', string='INSTAGRAM')
                if instagram_heading:
                    # Buscar o link do Instagram próximo a este cabeçalho
                    next_element = instagram_heading.find_next_sibling()
                    if next_element:
                        instagram_link = next_element.find('a', href=re.compile(r'instagram\.com'))
                        if instagram_link and 'camaradeputados' not in instagram_link.get('href', ''):
                            social_media['instagram'] = instagram_link.get('href')
            
            # Se não encontrou Instagram, tentar buscar na página inteira mas com filtros rígidos
            if not social_media['instagram']:
                all_instagram_links = soup.find_all('a', href=re.compile(r'instagram\.com'))
                for link in all_instagram_links:
                    href = link.get('href', '')
                    # Só aceitar se NÃO for o link oficial da Câmara
                    if ('/camaradeputados' not in href and 
                        'camaradeputados' not in href and
                        not href.endswith('/camaradeputados')):
                        social_media['instagram'] = href
                        break  # Pegar apenas o primeiro válido
            
            # Procurar especificamente pela div com classe "l-grid-social-media"
            social_media_div = soup.find('div', class_='l-grid-social-media')
            if social_media_div:
                logger.info(f"Encontrada div l-grid-social-media para deputado {deputado_id}")
                
                # Procurar por widgets de redes sociais que podem ter data-url* attributes
                widgets = social_media_div.find_all('div', class_=lambda x: x and 'widget-' in x)
                
                for widget in widgets:
                    
                    # Instagram widget
                    if 'widget-instagram' in widget.get('class', []):
                        instagram_handle = widget.get('data-urlinstagran') or widget.get('data-urlinstagram')
                        if instagram_handle and not social_media['instagram']:
                            # Construir URL completa do Instagram
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
                            # Verificar se não é o canal oficial da Câmara
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
                
                # Também verificar links tradicionais na div
                social_links = social_media_div.find_all('a', href=True)
                
                for link in social_links:
                    href = link.get('href', '')
                    
                    # Usar filtro abrangente para links oficiais
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
                    else:
                        pass
            
            # Se ainda não encontrou redes sociais, tentar busca na página inteira (como último recurso)
            if not any(social_media.values()):
                # Buscar por links fora da área de footer/rodapé
                main_content = soup.find('main') or soup.find('div', class_='content') or soup.body
                if main_content:
                    # Buscar links dentro do conteúdo principal, não no footer
                    links = main_content.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '').lower()
                    full_href = link.get('href', '')
                    
                    # Verificar se não está no footer (area com muitos links oficiais)
                    parent_classes = []
                    parent = link.parent
                    while parent and parent.name:
                        if parent.get('class'):
                            parent_classes.extend(parent.get('class'))
                        parent = parent.parent
                    
                    # Pular se estiver em área de footer/rodapé
                    if any('footer' in cls.lower() or 'rodape' in cls.lower() for cls in parent_classes):
                        logger.info(f"Link ignorado (está no footer): {full_href}")
                        continue
                    
                    # Debug: log todos os links de redes sociais encontrados
                    if any(platform in href for platform in ['facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'youtube.com', 'youtu.be', 'tiktok.com', 'linkedin.com']):
                        if 'instagram.com' in href:
                            pass
                    
                    # Facebook
                    if ('facebook.com' in href or 'fb.com' in href) and not social_media['facebook']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['facebook'] = link.get('href')
                        else:
                            pass
                    
                    # Twitter/X  
                    elif ('twitter.com' in href or 'x.com' in href) and not social_media['twitter']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['twitter'] = link.get('href')
                        else:
                            pass
                    
                    # Instagram - adicionado processamento no conteúdo principal
                    elif 'instagram.com' in href and not social_media['instagram']:
                        if not self._is_official_camara_link(full_href):
                            social_media['instagram'] = full_href
                        else:
                            pass
                    
                    # YouTube (com filtros rigorosos)
                    elif ('youtube.com' in href or 'youtu.be' in href) and not social_media['youtube']:
                        
                        if not self._is_official_camara_link(full_href):
                            social_media['youtube'] = full_href
                        else:
                            pass
                    
                    # TikTok
                    elif 'tiktok.com' in href and not social_media['tiktok']:
                        if '@camaradosdeputados' not in href:
                            social_media['tiktok'] = link.get('href')
                    
                    # LinkedIn
                    elif 'linkedin.com' in href and not social_media['linkedin']:
                        social_media['linkedin'] = link.get('href')
            
            # Fallback: buscar por links em toda a página se não encontrou na seção específica
            if not any(social_media.values()):
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href', '').lower()
                    
                    if 'facebook.com' in href and not social_media['facebook']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['facebook'] = link.get('href')
                        else:
                            pass
                    
                    elif ('twitter.com' in href or 'x.com' in href) and not social_media['twitter']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['twitter'] = link.get('href')
                        else:
                            pass
                    
                    elif 'instagram.com' in href and not social_media['instagram']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['instagram'] = link.get('href')
                        else:
                            pass
                    
                    elif ('youtube.com' in href or 'youtu.be' in href) and not social_media['youtube']:
                        full_href_for_check = link.get('href', '')
                        # Aplicar os mesmos filtros rigorosos da primeira busca
                        is_official = ('UC-ZkSRh-7UEuwXJQ9UMCFJA' in full_href_for_check or 
                                     'camaradeputados' in href or
                                     'camara.leg.br' in href)
                        
                        if not is_official:
                            social_media['youtube'] = full_href_for_check
                        else:
                            pass
                    
                    elif 'tiktok.com' in href and not social_media['tiktok']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['tiktok'] = link.get('href')
                        else:
                            pass
                    
                    elif 'linkedin.com' in href and not social_media['linkedin']:
                        if not self._is_official_camara_link(link.get('href')):
                            social_media['linkedin'] = link.get('href')
                        else:
                            pass
            
            # Log dos resultados
            found_links = [k for k, v in social_media.items() if v]
            if found_links:
                logger.info(f"Redes sociais encontradas para deputado {deputado_id}: {', '.join(found_links)}")
            else:
                logger.info(f"Nenhuma rede social encontrada para deputado {deputado_id}")
                
            return social_media
            
        except Exception as e:
            logger.error(f"Erro ao extrair redes sociais do deputado {deputado_id}: {str(e)}")
            return social_media
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Converte string de data para objeto datetime
        """
        if not date_str:
            return None
        
        try:
            # Formato da API: "YYYY-MM-DD"
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                # Formato alternativo: "DD/MM/YYYY"
                return datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                logger.warning(f"Formato de data inválido: {date_str}")
                return None
    
    def save_deputado(self, deputado_data: Dict, detalhes: Dict = None, social_media: Dict = None) -> Optional[Deputado]:
        """
        Salva ou atualiza dados de um deputado no banco
        """
        try:
            # Debug: verificar tipo dos dados
            if not isinstance(deputado_data, dict):
                logger.error(f"deputado_data deve ser um dict, recebido: {type(deputado_data)} - {deputado_data}")
                return None
            
            # Dados básicos da lista de deputados
            id_deputado = deputado_data.get('id')
            nome_parlamentar = deputado_data.get('nome', '')
            partido = deputado_data.get('siglaPartido', '')
            uf = deputado_data.get('siglaUf', '')
            uri = deputado_data.get('uri', '')
            foto_url = deputado_data.get('urlFoto', '')
            
            # Dados detalhados (se disponíveis)
            nome_civil = nome_parlamentar
            cpf = None
            data_nascimento = None
            naturalidade = None
            profissao = None
            escolaridade = None
            email = None
            telefone = None
            site = None
            gabinete = None
            biografia = None
            sexo = 'M'  # Default, will be updated with detailed data
            
            if detalhes:
                # Debug: verificar estrutura dos detalhes
                if not isinstance(detalhes, dict):
                    logger.error(f"detalhes deve ser um dict, recebido: {type(detalhes)} - {detalhes}")
                    detalhes = {}
                
                nome_civil = detalhes.get('nomeCivil', nome_parlamentar)
                cpf = detalhes.get('cpf', '')
                data_nascimento = self.parse_date(detalhes.get('dataNascimento', ''))
                naturalidade = detalhes.get('municipioNascimento', '')
                if naturalidade and detalhes.get('ufNascimento'):
                    naturalidade += f" - {detalhes.get('ufNascimento')}"
                profissao = detalhes.get('profissao', '')
                escolaridade = detalhes.get('escolaridade', '')
                
                # Buscar email e telefone no ultimoStatus.gabinete (local correto na API)
                ultimo_status = detalhes.get('ultimoStatus', {})
                if isinstance(ultimo_status, dict):
                    gabinete_info = ultimo_status.get('gabinete', {})
                    if isinstance(gabinete_info, dict):
                        email = gabinete_info.get('email', '')
                        telefone = gabinete_info.get('telefone', '')
                        gabinete = gabinete_info.get('sala', '')
                    else:
                        email = ''
                        telefone = ''
                        gabinete = ''
                else:
                    email = ''
                    telefone = ''
                    gabinete = ''
                
                # Processar redes sociais dos detalhes com cuidado
                rede_social = detalhes.get('redeSocial', [])
                if isinstance(rede_social, list) and rede_social:
                    # redeSocial é uma lista de URLs, pegar a primeira como site se disponível
                    site = rede_social[0] if rede_social else ''
                else:
                    site = ''
                    
                sexo = 'M' if detalhes.get('sexo', '').upper() == 'M' else 'F'
            
            # Dados de redes sociais (se disponíveis)
            facebook_url = None
            twitter_url = None
            instagram_url = None
            youtube_url = None
            tiktok_url = None
            linkedin_url = None
            
            if social_media:
                # Debug: verificar estrutura das redes sociais
                if not isinstance(social_media, dict):
                    logger.error(f"social_media deve ser um dict, recebido: {type(social_media)} - {social_media}")
                    social_media = {}
                
                facebook_url = social_media.get('facebook')
                twitter_url = social_media.get('twitter')
                instagram_url = social_media.get('instagram')
                youtube_url = social_media.get('youtube')
                tiktok_url = social_media.get('tiktok')
                linkedin_url = social_media.get('linkedin')
            
            # Criar ou atualizar deputado
            deputado, created = Deputado.objects.update_or_create(
                id_deputado_camara=id_deputado,
                defaults={
                    'nome_civil': nome_civil,
                    'nome_parlamentar': nome_parlamentar,
                    'cpf': cpf if cpf else None,
                    'partido': partido,
                    'uf': uf,
                    'sexo': sexo,
                    'data_nascimento': data_nascimento,
                    'naturalidade': naturalidade,
                    'profissao': profissao,
                    'escolaridade': escolaridade,
                    'email': email if email else None,
                    'telefone': telefone,
                    'site': site if site else None,
                    'gabinete': gabinete,
                    'biografia': biografia,
                    'foto_url': foto_url if foto_url else None,
                    'uri_camara': uri,
                    'facebook_url': facebook_url,
                    'twitter_url': twitter_url,
                    'instagram_url': instagram_url,
                    'youtube_url': youtube_url,
                    'tiktok_url': tiktok_url,
                    'linkedin_url': linkedin_url,
                    'is_active': True,
                    'updated_at': timezone.now()
                }
            )
            
            if created:
                logger.info(f"Criado novo deputado: {nome_parlamentar}")
            else:
                logger.info(f"Atualizado deputado: {nome_parlamentar}")
                
            return deputado
            
        except Exception as e:
            logger.error(f"Erro ao salvar deputado {deputado_data.get('nome', '') if isinstance(deputado_data, dict) else 'N/A'}: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def save_mandatos(self, deputado: Deputado, mandatos_data: List[Dict]):
        """
        Salva histórico de mandatos de um deputado
        """
        for mandato_data in mandatos_data:
            try:
                legislatura = mandato_data.get('idLegislatura', '')
                data_inicio = self.parse_date(mandato_data.get('dataInicio', ''))
                data_fim = self.parse_date(mandato_data.get('dataFim', ''))
                situacao = mandato_data.get('situacao', '')
                condicao = mandato_data.get('condicaoEleitoral', '')
                
                HistoricoMandato.objects.update_or_create(
                    deputado=deputado,
                    legislatura=str(legislatura),
                    defaults={
                        'data_inicio': data_inicio,
                        'data_fim': data_fim,
                        'situacao': situacao,
                        'condicao': condicao,
                        'updated_at': timezone.now()
                    }
                )
                
            except Exception as e:
                logger.error(f"Erro ao salvar mandato do deputado {deputado.nome_parlamentar}: {str(e)}")
    
    def extract_legislatura_57(self, with_details: bool = True, limit: Optional[int] = None):
        """
        Extrai dados dos deputados da 57ª legislatura (API + web scraping)
        
        Args:
            with_details: Se True, obtém dados detalhados de cada deputado (mais lento)
            limit: Limite de deputados para processar (para testes)
        """
        logger.info("Iniciando extração de dados para a 57ª legislatura...")
        
        # ID da 57ª legislatura (2023-2027)
        legislatura_57_id = 57
        
        # Obter lista de deputados
        deputados = self.get_deputados_by_legislatura(legislatura_57_id)
        
        if not deputados:
            logger.error("Não foi possível obter lista de deputados da 57ª legislatura")
            return
        
        logger.info(f"Encontrados {len(deputados)} deputados na 57ª legislatura")
        
        # Aplicar limite se especificado
        if limit:
            deputados = deputados[:limit]
            logger.info(f"Processando apenas os primeiros {limit} deputados")
        
        processed = 0
        errors = 0
        
        for deputado_data in deputados:
            try:
                id_deputado = deputado_data.get('id')
                nome = deputado_data.get('nome', '')
                
                logger.info(f"Processando {nome} (ID: {id_deputado})...")
                
                # Obter detalhes se solicitado
                detalhes = None
                if with_details:
                    detalhes = self.get_deputado_detalhes(id_deputado)
                
                # Extrair redes sociais
                logger.info(f"Extraindo redes sociais de {nome}...")
                social_media = self.extract_social_media_links(id_deputado)
                
                # Salvar deputado
                deputado = self.save_deputado(deputado_data, detalhes, social_media)
                
                if deputado:
                    # Marcar como sendo da 57ª legislatura
                    deputado.legislatura = "57"
                    deputado.save()
                    
                    # Obter e salvar histórico de mandatos
                    mandatos = self.get_deputado_mandatos(id_deputado)
                    if mandatos:
                        self.save_mandatos(deputado, mandatos)
                    
                    processed += 1
                else:
                    errors += 1
                
                # Pausa para não sobrecarregar o servidor (API + scraping)
                import time
                time.sleep(1.5)  # Aumentado para não sobrecarregar com scraping
                
            except Exception as e:
                logger.error(f"Erro ao processar deputado {nome}: {str(e)}")
                errors += 1
                continue
        
        logger.info(f"Extração finalizada. Processados: {processed}, Erros: {errors}")
    
    def extract_all_legislaturas(self, with_details: bool = False):
        """
        Extrai dados de todas as legislaturas disponíveis (API + web scraping)
        """
        logger.info("Obtendo lista de legislaturas...")
        
        legislaturas = self.get_legislaturas()
        
        for legislatura in legislaturas:
            legislatura_id = legislatura.get('id')
            legislatura_nome = legislatura.get('id')  # O ID é o número da legislatura
            
            logger.info(f"Processando legislatura {legislatura_nome}...")
            
            deputados = self.get_deputados_by_legislatura(legislatura_id)
            
            for deputado_data in deputados:
                try:
                    detalhes = None
                    if with_details:
                        detalhes = self.get_deputado_detalhes(deputado_data.get('id'))
                    
                    deputado = self.save_deputado(deputado_data, detalhes)
                    
                    if deputado:
                        deputado.legislatura = str(legislatura_nome)
                        deputado.save()
                    
                    # Pausa para não sobrecarregar a API
                    import time
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar deputado da legislatura {legislatura_nome}: {str(e)}")
                    continue


def extract_57th_legislature_data(with_details: bool = True, limit: Optional[int] = None):
    """
    Função principal para extrair dados da 57ª legislatura
    """
    extractor = DeputadosDataExtractor()
    extractor.extract_legislatura_57(with_details=with_details, limit=limit)


def extract_all_legislatures_data(with_details: bool = False):
    """
    Função principal para extrair dados de todas as legislaturas
    """
    extractor = DeputadosDataExtractor()
    extractor.extract_all_legislaturas(with_details=with_details)