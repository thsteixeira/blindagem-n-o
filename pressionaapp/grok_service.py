"""
Grok API Service for Twitter/X profile discovery
Handles Twitter profile discovery using Grok API with live search
"""

import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings
import re

logger = logging.getLogger(__name__)


class GrokAPIError(Exception):
    """Custom exception for Grok API errors"""
    pass


class GrokTwitterService:
    """
    Service class for Twitter/X profile discovery using Grok API
    Focuses on finding and verifying Twitter profiles of Brazilian politicians
    """
    
    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        if not self.api_key:
            raise ValueError("GROK_API_KEY not found in settings. Please set it in your .env file.")
        
        # Base configuration for Grok API calls
        self.base_headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'PressionaApp/1.0'
        }
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.base_headers)
        
        # Rate limiting and retry configuration
        self.max_retries = 3
        self.retry_delay = 2  # Base for exponential backoff
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict:
        """
        Make a request to Grok API with error handling and retries
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: API endpoint URL
            **kwargs: Additional arguments for requests
            
        Returns:
            API response as dictionary
            
        Raises:
            GrokAPIError: If API request fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Handle different response codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise GrokAPIError("Invalid API key or unauthorized access")
                elif response.status_code == 403:
                    raise GrokAPIError("Access forbidden - check API permissions")
                elif response.status_code == 429:
                    # Rate limited - wait and retry with exponential backoff
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(self.retry_delay ** (attempt + 1))  # 2, 4, 8 seconds
                        continue
                    raise GrokAPIError("Rate limit exceeded - please try again later")
                elif response.status_code >= 500:
                    # Server error - retry with exponential backoff
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(self.retry_delay ** (attempt + 1))  # 2, 4, 8 seconds
                        continue
                    raise GrokAPIError(f"Server error: {response.status_code}")
                else:
                    raise GrokAPIError(f"Unexpected response code: {response.status_code}")
                    
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise GrokAPIError(f"Request failed: {str(e)}")
        
        raise GrokAPIError("Max retries exceeded")
    
    def find_twitter_profile(self, nome: str, nome_parlamentar: str, role: str = "deputado", 
                           additional_context: str = None) -> Optional[Dict[str, any]]:
        """
        Find Twitter/X profile using Grok API
        
        Args:
            nome: Full name of the person
            nome_parlamentar: Parliamentary name
            role: Role (deputado/senador)
            additional_context: Additional context like party, state, etc.
            
        Returns:
            Dictionary with profile information or None if not found
        """
        try:
            # Build enhanced search query similar to successful browser query
            search_terms = []
            
            # Add names in quotes for exact matching
            if nome_parlamentar:
                search_terms.append(f'"{nome_parlamentar}"')
            if nome and nome.lower() != nome_parlamentar.lower():
                search_terms.append(f'"{nome}"')
            
            # Add role and Brazilian context
            search_terms.append(f"{role} brasileiro")
            
            # Add additional context if provided
            if additional_context:
                search_terms.append(additional_context)
            
            # Add platform and official context (Portuguese + English)
            search_terms.extend(["Twitter", "X.com", "perfil oficial", "conta oficial"])
            
            query = " ".join(search_terms)
            
            logger.info(f"Searching for Twitter profile via Grok with live search: {query}")
            
            # Real Grok API call for Twitter profile search
            try:
                # Enhanced system message emphasizing official accounts
                system_message = """You are a search assistant specialized in finding OFFICIAL social media profiles of Brazilian politicians.

IMPORTANT: Always prioritize OFFICIAL political accounts over personal ones. Use tools like x_user_search or x_keyword_search for precise X/Twitter lookups. Look for verified profiles with political bios and government content.

Use live search with site:x.com for real-time data. Return ONLY valid JSON with actual data. No extra text, markdown, or explanations."""

                # Enhanced user message with Portuguese context (like successful browser query)
                user_message = f"""Encontre o perfil oficial no X (antigo Twitter) do político brasileiro:

Nome: {nome}
Nome parlamentar: {nome_parlamentar}
Cargo: {role}
{f"Contexto: {additional_context}" if additional_context else ""}

Procure por:
- Contas verificadas com bio mencionando cargo/estado/partido
- Atividade política recente
- Use ferramentas como x_user_search para o username exato

Responda APENAS com o JSON na estrutura exata, envolto em <json> </json> tags:
<json>
{{
    "status": "success",
    "results": [
        {{
            "platform": "twitter",
            "url": "https://x.com/username",
            "username": "username_without_@",
            "display_name": "Display Name",
            "verified": true/false,
            "confidence_score": 0.0-1.0,
            "profile_description": "bio text",
            "follower_count": number,
            "following_count": number,
            "tweet_count": number
        }}
    ]
}}
</json>

Se não encontrado, use {{"status": "not_found", "results": []}}."""

                # API call with optimized parameters for accuracy
                api_payload = {
                    "model": "grok-4-fast-reasoning",  # More precise for complex searches
                    "messages": [
                        {
                            "role": "system", 
                            "content": system_message
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1500,  # Increased for longer responses
                    "search_parameters": {
                        "enabled": True,
                        "num_sources": 5  # Limit sources for cost control and focus
                    }
                }
                
                # Make API call with live search enabled
                logger.info("Making Grok API call with live search enabled...")
                response = self._make_request('POST', 'https://api.x.ai/v1/chat/completions', json=api_payload)
                
                # Parse the response to extract JSON from Grok's response
                content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                logger.info(f"Grok profile response: {content}")
                
                # Check if response is empty or just whitespace
                if not content or not content.strip():
                    logger.warning("Grok API returned empty response")
                    raise ValueError("Empty response from Grok API")
                
                # Enhanced JSON parsing with XML tag handling
                import json
                import re
                
                # Strip XML tags or markdown
                content = content.strip()
                if content.startswith('<json>') and content.endswith('</json>'):
                    content = content.replace('<json>', '').replace('</json>', '').strip()
                elif content.startswith('```json') and content.endswith('```'):
                    content = content.strip('```json').strip('```').strip()
                
                try:
                    parsed_json = json.loads(content)
                    logger.info(f"Parsed JSON: {parsed_json}")
                except json.JSONDecodeError:
                    # Fallback to regex extraction
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            parsed_json = json.loads(json_match.group())
                            logger.info(f"Parsed JSON via regex: {parsed_json}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON from Grok response: {e}")
                            raise ValueError(f"Invalid JSON in Grok response: {e}")
                    else:
                        raise ValueError("No valid JSON found in Grok response")
                
                # Check if this is a direct profile response (simple format)
                if 'username' in parsed_json:
                    # Generate URL from username if not provided
                    username = parsed_json.get("username")
                    profile_url = parsed_json.get("url", f"https://x.com/{username}")
                    
                    # Convert simple response to expected format
                    api_response = {
                        "status": "success",
                        "results": [{
                            "platform": "twitter",
                            "url": profile_url,
                            "username": username,
                            "display_name": parsed_json.get("display_name", ""),
                            "verified": parsed_json.get("verified", False),
                            "confidence_score": 0.9,  # High confidence for direct matches
                            "profile_description": parsed_json.get("bio", ""),
                            "follower_count": parsed_json.get("follower_count", parsed_json.get("followers", 0)),
                            "following_count": parsed_json.get("following_count", parsed_json.get("following", 0)),
                            "tweet_count": parsed_json.get("tweet_count", parsed_json.get("tweets", 0))
                        }]
                    }
                else:
                    # Use original format if it matches expected structure
                    api_response = parsed_json
                    
            except requests.exceptions.Timeout:
                logger.error("Grok API request timed out (live search with x_user_search may be slow)")
                api_response = {"status": "timeout", "results": []}
            except requests.exceptions.ConnectionError:
                logger.error("Failed to connect to Grok API")
                api_response = {"status": "connection_error", "results": []}
            except GrokAPIError as e:
                logger.error(f"Grok API error (check live search permissions): {str(e)}")
                api_response = {"status": "api_error", "results": []}
            except Exception as e:
                logger.error(f"Unexpected error in profile search with live search: {str(e)}")
                api_response = {"status": "error", "results": []}
            
            # Process Grok response
            if api_response.get("status") == "success" and api_response.get("results"):
                results = api_response["results"]
                
                # Filter and prioritize verified/official accounts
                twitter_profiles = [r for r in results if r.get("platform") == "twitter"]
                
                # Prioritize verified accounts first
                verified_profiles = [r for r in twitter_profiles if r.get("verified", False)]
                unverified_profiles = [r for r in twitter_profiles if not r.get("verified", False)]
                
                # Sort each group by confidence
                verified_profiles.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
                unverified_profiles.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
                
                # Combine: verified first, then unverified
                twitter_profiles = verified_profiles + unverified_profiles
                
                if twitter_profiles:
                    best_match = twitter_profiles[0]
                    
                    profile_info = {
                        'url': best_match.get('url'),
                        'username': best_match.get('username'),
                        'display_name': best_match.get('display_name'),
                        'verified': best_match.get('verified', False),
                        'confidence_score': best_match.get('confidence_score', 0),
                        'source': 'grok_api',
                        'metadata': {
                            'profile_description': best_match.get('profile_description'),
                            'follower_count': best_match.get('follower_count'),
                            'following_count': best_match.get('following_count'),
                            'tweet_count': best_match.get('tweet_count')
                        }
                    }
                    
                    logger.info(f"Found Twitter profile via Grok: {profile_info['url']} (confidence: {profile_info['confidence_score']})")
                    return profile_info
            
            logger.info(f"No Twitter profile found via Grok for {nome_parlamentar}")
            return None
            
        except GrokAPIError as e:
            logger.error(f"Grok API error finding Twitter profile for {nome_parlamentar}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding Twitter profile for {nome_parlamentar}: {str(e)}")
            return None
    
    def verify_profile_authenticity(self, profile_url: str, nome: str, nome_parlamentar: str) -> Dict[str, any]:
        """
        Use Grok AI to verify if a Twitter profile is authentic for a given person
        
        Args:
            profile_url: Twitter profile URL to verify
            nome: Full name of the person
            nome_parlamentar: Parliamentary name
            
        Returns:
            Dictionary with verification results
        """
        try:
            logger.info(f"Verifying profile authenticity via Grok: {profile_url}")
            
            # Real Grok API call for verification
            system_message = """You are an authenticity verifier for X profiles of Brazilian politicians. Analyze the profile and return ONLY JSON with verification details."""
            
            user_message = f"""Analise o perfil: {profile_url}
Detalhes: Nome {nome}, Parlamentar {nome_parlamentar}.

Verifique: nome match, bio política, conteúdo consistente, verificado, idade da conta.

Responda APENAS com JSON:
<json>
{{
    "is_authentic": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "explicação",
    "verification_status": "verified/not_verified",
    "red_flags": ["lista"],
    "positive_indicators": ["lista"]
}}
</json>"""
            
            api_payload = {
                "model": "grok-4-fast-reasoning",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
                "search_parameters": {"enabled": True, "num_sources": 3}
            }
            
            response = self._make_request('POST', 'https://api.x.ai/v1/chat/completions', json=api_payload)
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Parse JSON response
            content = content.strip()
            if content.startswith('<json>') and content.endswith('</json>'):
                content = content.replace('<json>', '').replace('</json>', '').strip()
            
            import json
            verification_result = json.loads(content)
            
            logger.info(f"Profile verification complete: {verification_result['confidence_score']} confidence")
            return verification_result
            
        except Exception as e:
            logger.error(f"Error verifying profile authenticity: {str(e)}")
            return {
                'is_authentic': False,
                'confidence_score': 0.0,
                'reasoning': f'Verification failed: {str(e)}',
                'error': str(e)
            }
    
    def __del__(self):
        """Clean up session when service is destroyed"""
        if hasattr(self, 'session'):
            self.session.close()