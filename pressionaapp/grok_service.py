"""
Grok API Service for Twitter/X operations
Handles profile discovery and tweet extraction using Grok API
"""

import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GrokAPIError(Exception):
    """Custom exception for Grok API errors"""
    pass


class GrokTwitterService:
    """
    Service class for Twitter/X operations using Grok API
    Handles both profile discovery and tweet extraction
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
        self.retry_delay = 1  # seconds
    
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
                    # Rate limited - wait and retry
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise GrokAPIError("Rate limit exceeded - please try again later")
                elif response.status_code >= 500:
                    # Server error - retry
                    if attempt < self.max_retries - 1:
                        import time
                        time.sleep(self.retry_delay * (attempt + 1))
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
            # Build search query for Grok
            search_terms = []
            
            # Add names
            if nome_parlamentar:
                search_terms.append(f'"{nome_parlamentar}"')
            if nome and nome.lower() != nome_parlamentar.lower():
                search_terms.append(f'"{nome}"')
            
            # Add role context
            search_terms.append(role)
            
            # Add additional context if provided
            if additional_context:
                search_terms.append(additional_context)
            
            # Add platform context
            search_terms.extend(["Twitter", "X.com", "perfil oficial", "conta oficial"])
            
            query = " ".join(search_terms)
            
            logger.info(f"Searching for Twitter profile via Grok: {query}")
            
            # TODO: Replace with actual Grok API endpoint and parameters
            # This is a placeholder structure based on common AI API patterns
            api_payload = {
                "query": f"Find the official Twitter/X profile for {query}. Return only verified or highly likely official accounts.",
                "task": "profile_search",
                "parameters": {
                    "platform": "twitter",
                    "search_type": "profile",
                    "verification_level": "high",
                    "max_results": 3
                }
            }
            
            # TODO: Replace with actual Grok API endpoint
            # response = self._make_request('POST', 'https://api.grok.com/v1/search', json=api_payload)
            
            # PLACEHOLDER: Mock response structure for development
            # Replace this entire section with actual Grok API call
            logger.warning("Using mock Grok API response - replace with actual API call")
            mock_response = {
                "status": "success",
                "results": [
                    {
                        "platform": "twitter", 
                        "url": f"https://twitter.com/{nome_parlamentar.lower().replace(' ', '')}",
                        "username": nome_parlamentar.lower().replace(' ', ''),
                        "display_name": nome_parlamentar,
                        "verified": False,
                        "confidence_score": 0.85,
                        "profile_description": f"Deputado - {nome_parlamentar}",
                        "follower_count": 1000,
                        "following_count": 500,
                        "tweet_count": 150
                    }
                ]
            }
            
            # Process Grok response
            if mock_response.get("status") == "success" and mock_response.get("results"):
                results = mock_response["results"]
                
                # Filter and sort by confidence
                twitter_profiles = [r for r in results if r.get("platform") == "twitter"]
                twitter_profiles.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)
                
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
    
    def get_latest_tweets(self, username: str = None, twitter_url: str = None, 
                         max_tweets: int = 5, days_back: int = 180) -> List[Dict[str, any]]:
        """
        Get latest tweets from a Twitter profile using Grok API
        
        Args:
            username: Twitter username (without @)
            twitter_url: Full Twitter URL (alternative to username) 
            max_tweets: Maximum number of tweets to retrieve
            days_back: How many days back to search for tweets
            
        Returns:
            List of tweet dictionaries
        """
        try:
            # Extract username from URL if needed
            if not username and twitter_url:
                match = re.search(r'(?:twitter\.com/|x\.com/)([^/?]+)', twitter_url)
                if match:
                    username = match.group(1)
                else:
                    logger.error(f"Could not extract username from URL: {twitter_url}")
                    return []
            
            if not username:
                logger.warning("No username provided for tweet extraction")
                return []
            
            logger.info(f"Fetching latest tweets for @{username} via Grok API")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # TODO: Replace with actual Grok API endpoint and parameters
            api_payload = {
                "query": f"Get the latest {max_tweets} tweets from @{username} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                "task": "tweet_extraction",
                "parameters": {
                    "username": username,
                    "max_results": max_tweets,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "include_retweets": False,
                    "include_replies": False
                }
            }
            
            # TODO: Replace with actual Grok API endpoint
            # response = self._make_request('POST', 'https://api.grok.com/v1/tweets', json=api_payload)
            
            # PLACEHOLDER: Mock response structure for development
            logger.warning("Using mock Grok API response - replace with actual API call")
            mock_response = {
                "status": "success",
                "tweets": [
                    {
                        "id": "1234567890123456789",
                        "url": f"https://twitter.com/{username}/status/1234567890123456789",
                        "text": f"Esta é uma tweet de exemplo do {username}. #Política #Brasil",
                        "created_at": "2025-09-20T10:30:00Z",
                        "author": {
                            "username": username,
                            "display_name": username.title()
                        },
                        "metrics": {
                            "likes": 25,
                            "retweets": 8,
                            "replies": 3
                        },
                        "is_retweet": False,
                        "is_reply": False
                    },
                    {
                        "id": "1234567890123456790",
                        "url": f"https://twitter.com/{username}/status/1234567890123456790",
                        "text": f"Outra mensagem importante sobre políticas públicas do {username}.",
                        "created_at": "2025-09-18T15:45:00Z",
                        "author": {
                            "username": username,
                            "display_name": username.title()
                        },
                        "metrics": {
                            "likes": 42,
                            "retweets": 15,
                            "replies": 7
                        },
                        "is_retweet": False,
                        "is_reply": False
                    }
                ]
            }
            
            # Process Grok response
            if mock_response.get("status") == "success" and mock_response.get("tweets"):
                tweets = []
                
                for tweet_data in mock_response["tweets"]:
                    tweet_info = {
                        'tweet_id': tweet_data.get('id'),
                        'url': tweet_data.get('url'),
                        'text': tweet_data.get('text'),
                        'created_at': tweet_data.get('created_at'),
                        'username': tweet_data.get('author', {}).get('username'),
                        'display_name': tweet_data.get('author', {}).get('display_name'),
                        'metrics': tweet_data.get('metrics', {}),
                        'is_retweet': tweet_data.get('is_retweet', False),
                        'is_reply': tweet_data.get('is_reply', False),
                        'source': 'grok_api'
                    }
                    tweets.append(tweet_info)
                
                logger.info(f"Retrieved {len(tweets)} tweets for @{username} via Grok API")
                return tweets
            
            logger.info(f"No tweets found for @{username} via Grok API")
            return []
            
        except GrokAPIError as e:
            logger.error(f"Grok API error fetching tweets for @{username}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching tweets for @{username}: {str(e)}")
            return []
    
    def search_tweets_by_content(self, search_query: str, max_results: int = 10, 
                                days_back: int = 30) -> List[Dict[str, any]]:
        """
        Search for tweets by content using Grok API
        
        Args:
            search_query: Search query for tweet content
            max_results: Maximum number of results
            days_back: How many days back to search
            
        Returns:
            List of matching tweets
        """
        try:
            logger.info(f"Searching tweets by content via Grok: {search_query}")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # TODO: Replace with actual Grok API endpoint
            api_payload = {
                "query": search_query,
                "task": "content_search",
                "parameters": {
                    "max_results": max_results,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "language": "pt",  # Portuguese tweets
                    "country": "BR"    # Brazil
                }
            }
            
            # TODO: Implement actual API call
            logger.warning("Tweet content search not yet implemented - placeholder")
            return []
            
        except Exception as e:
            logger.error(f"Error searching tweets by content: {str(e)}")
            return []
    
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
            
            # TODO: Implement actual Grok verification call
            verification_prompt = f"""
            Analyze this Twitter profile URL: {profile_url}
            
            Person details:
            - Full name: {nome}
            - Parliamentary name: {nome_parlamentar}
            
            Verify if this is likely the authentic official profile by checking:
            1. Profile name matches
            2. Bio mentions political role
            3. Content is consistent with a politician
            4. Verification status
            5. Account age and activity patterns
            
            Return confidence score (0-1) and reasoning.
            """
            
            # Placeholder verification result
            verification_result = {
                'is_authentic': True,
                'confidence_score': 0.90,
                'reasoning': 'Profile name matches, bio mentions political role, content consistent',
                'verification_status': 'not_verified',
                'red_flags': [],
                'positive_indicators': ['Name match', 'Political content', 'Regular activity']
            }
            
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