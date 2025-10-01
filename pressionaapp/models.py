from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Tweet(models.Model):
    """
    Model to store latest tweets from deputies and senators
    """
    # Generic relation to link to either Deputado or Senador
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    parliamentarian = GenericForeignKey('content_type', 'object_id')
    
    # Tweet information
    tweet_url = models.URLField(verbose_name="URL do Tweet")
    tweet_id = models.CharField(max_length=50, verbose_name="ID do Tweet")
    
    # Tweet metadata (extracted from URL or API if available)
    discovered_at = models.DateTimeField(auto_now_add=True, verbose_name="Descoberto em")
    position = models.PositiveSmallIntegerField(verbose_name="Posição", 
                                               help_text="1=mais recente, 5=mais antigo")
    
    # Tweet content (optional - can be filled later by API)
    tweet_text = models.TextField(null=True, blank=True, verbose_name="Texto do Tweet")
    tweet_date = models.DateTimeField(null=True, blank=True, verbose_name="Data do Tweet")
    
    # Metadata
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    needs_content_update = models.BooleanField(default=True, verbose_name="Precisa Atualizar Conteúdo")
    
    class Meta:
        verbose_name = "Tweet"
        verbose_name_plural = "Tweets"
        ordering = ['content_type', 'object_id', 'position']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['position']),
            models.Index(fields=['discovered_at']),
            models.Index(fields=['is_active']),
        ]
        # Ensure unique tweets per parliamentarian
        unique_together = [
            ('content_type', 'object_id', 'tweet_id'),
            ('content_type', 'object_id', 'position'),
        ]
    
    def __str__(self):
        return f"Tweet {self.position} - {self.parliamentarian} ({self.tweet_id})"
    
    @property
    def is_latest(self):
        """Check if this is the latest tweet (position 1)"""
        return self.position == 1
    
    def get_twitter_reply_link(self, message=None):
        """Generate a Twitter reply link for this specific tweet"""
        if not message:
            parliamentarian_name = getattr(self.parliamentarian, 'nome_parlamentar', 'Parlamentar')
            message = f"Olá {parliamentarian_name}! Gostaria de dialogar sobre suas propostas. #TransparênciaPolítica"
        
        from urllib.parse import quote
        encoded_message = quote(message)
        return f"https://twitter.com/intent/tweet?in_reply_to={self.tweet_id}&text={encoded_message}"


class TwitterMessage(models.Model):
    """
    Model to store custom messages that can be sent through Twitter
    """
    CATEGORY_CHOICES = [
        ('greeting', 'Saudação'),
        ('question', 'Pergunta'),
        ('opinion', 'Opinião'),
        ('complaint', 'Reclamação'),
        ('suggestion', 'Sugestão'),
        ('support', 'Apoio'),
        ('criticism', 'Crítica'),
        ('information_request', 'Solicitação de Informação'),
        ('other', 'Outro'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Rascunho'),
        ('ready', 'Pronto para Envio'),
        ('sent', 'Enviado'),
        ('failed', 'Falha no Envio'),
        ('archived', 'Arquivado'),
    ]
    
    # Message Content
    title = models.CharField(max_length=100, verbose_name="Título da Mensagem")
    message = models.TextField(max_length=280, verbose_name="Mensagem", 
                              help_text="Máximo 280 caracteres (limite do Twitter)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, 
                               default='other', verbose_name="Categoria")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, 
                               default='medium', verbose_name="Prioridade")
    
    # Message Metadata
    hashtags = models.CharField(max_length=200, null=True, blank=True, 
                               verbose_name="Hashtags", 
                               help_text="Hashtags separadas por espaço (ex: #política #transparência)")
    mentions = models.CharField(max_length=200, null=True, blank=True, 
                               verbose_name="Menções", 
                               help_text="Usuários a mencionar separados por espaço (ex: @usuario1 @usuario2)")
    
    # Target Audience
    for_deputies = models.BooleanField(default=True, verbose_name="Para Deputados")
    for_senators = models.BooleanField(default=True, verbose_name="Para Senadores")
    target_parties = models.CharField(max_length=500, null=True, blank=True, 
                                     verbose_name="Partidos Alvo", 
                                     help_text="Partidos específicos separados por vírgula (deixe vazio para todos)")
    target_states = models.CharField(max_length=100, null=True, blank=True, 
                                    verbose_name="Estados Alvo", 
                                    help_text="Estados específicos separados por vírgula (deixe vazio para todos)")
    
    # System fields
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, 
                             default='draft', verbose_name="Status")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  verbose_name="Criado por", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    scheduled_for = models.DateTimeField(null=True, blank=True, 
                                        verbose_name="Agendado para")
    sent_at = models.DateTimeField(null=True, blank=True, 
                                  verbose_name="Enviado em")
    
    # Usage tracking
    times_used = models.PositiveIntegerField(default=0, verbose_name="Vezes Utilizada")
    last_used_at = models.DateTimeField(null=True, blank=True, 
                                       verbose_name="Última vez utilizada")
    
    class Meta:
        verbose_name = "Mensagem do Twitter"
        verbose_name_plural = "Mensagens do Twitter"
        ordering = ['-created_at', 'priority']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
    
    @property
    def character_count(self):
        """Return the character count of the message"""
        return len(self.message)
    
    @property
    def is_within_twitter_limit(self):
        """Check if message is within Twitter's character limit"""
        return self.character_count <= 280
    
    @property
    def remaining_characters(self):
        """Return remaining characters for Twitter limit"""
        return 280 - self.character_count
    
    def get_formatted_message(self, parliamentarian_name=None):
        """Get the formatted message with mentions and hashtags"""
        formatted_message = self.message
        
        # Add parliamentarian mention if provided
        if parliamentarian_name:
            formatted_message = f"@{parliamentarian_name} {formatted_message}"
        
        # Add mentions if specified
        if self.mentions:
            formatted_message = f"{formatted_message} {self.mentions}"
        
        # Add hashtags if specified
        if self.hashtags:
            formatted_message = f"{formatted_message} {self.hashtags}"
        
        return formatted_message
    
    def mark_as_used(self):
        """Mark message as used and update usage statistics"""
        self.times_used += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['times_used', 'last_used_at'])
    
    def can_be_sent_to_parliamentarian(self, parliamentarian):
        """Check if this message can be sent to a specific parliamentarian"""
        # Check if message is ready
        if self.status != 'ready':
            return False
        
        # Check parliamentarian type
        if hasattr(parliamentarian, 'partido'):  # Check if it's a Deputy or Senator
            if 'Deputado' in str(type(parliamentarian)) and not self.for_deputies:
                return False
            if 'Senador' in str(type(parliamentarian)) and not self.for_senators:
                return False
        
        # Check party filter
        if self.target_parties:
            target_parties = [p.strip().upper() for p in self.target_parties.split(',')]
            if parliamentarian.partido.upper() not in target_parties:
                return False
        
        # Check state filter
        if self.target_states:
            target_states = [s.strip().upper() for s in self.target_states.split(',')]
            if parliamentarian.uf.upper() not in target_states:
                return False
        
        return True


class Deputado(models.Model):
    """
    Simplified model for Brazilian deputies (active congressmen only)
    Stores only essential contact and political information
    """
    # Political Identity (required)
    nome_parlamentar = models.CharField(max_length=255, verbose_name="Nome Parlamentar")
    partido = models.CharField(max_length=50, verbose_name="Partido")
    uf = models.CharField(max_length=2, verbose_name="Estado (UF)")
    
    # Contact Information
    email = models.EmailField(null=True, blank=True, verbose_name="Email")
    telefone = models.CharField(max_length=50, null=True, blank=True, verbose_name="Telefone")
    foto_url = models.URLField(null=True, blank=True, verbose_name="Foto")
    
    # Twitter-only Social Media
    twitter_url = models.URLField(null=True, blank=True, verbose_name="Twitter/X")
    
    # Latest Tweet Information
    latest_tweet_url = models.URLField(null=True, blank=True, verbose_name="Último Tweet")
    
    # Social Media Source Tracking
    SOCIAL_MEDIA_SOURCE_CHOICES = [
        ('official_api', 'API Oficial'),
        ('chamber_website', 'Site da Câmara'),
        ('grok_api', 'Grok API'),
        ('google_search', 'Google Search'),
        ('manual', 'Manual'),
    ]
    
    SOCIAL_MEDIA_CONFIDENCE_CHOICES = [
        ('high', 'Alta'),
        ('medium', 'Média'),
        ('low', 'Baixa'),
    ]
    
    social_media_source = models.CharField(
        max_length=50, null=True, blank=True, 
        choices=SOCIAL_MEDIA_SOURCE_CHOICES,
        verbose_name="Fonte das Redes Sociais",
        help_text="Fonte de onde foi extraída a informação das redes sociais"
    )
    social_media_confidence = models.CharField(
        max_length=20, null=True, blank=True,
        choices=SOCIAL_MEDIA_CONFIDENCE_CHOICES,
        verbose_name="Confiança das Redes Sociais", 
        help_text="Nível de confiança da informação das redes sociais"
    )
    needs_social_media_review = models.BooleanField(
        default=False, verbose_name="Precisa Revisar Redes Sociais"
    )
    
    # System fields (for API integration)
    api_id = models.IntegerField(unique=True, verbose_name="ID na API da Câmara")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Deputado"
        verbose_name_plural = "Deputados"
        ordering = ['nome_parlamentar']
        indexes = [
            models.Index(fields=['partido']),
            models.Index(fields=['uf']),
            models.Index(fields=['nome_parlamentar']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.nome_parlamentar} ({self.partido}/{self.uf})"
    
    @property
    def has_twitter(self):
        """Check if deputy has Twitter account"""
        return bool(self.twitter_url)
    
    @property
    def has_social_media(self):
        """Alias for has_twitter for template compatibility"""
        return self.has_twitter
    
    def get_twitter_reply_link(self, message=None):
        """Generate a Twitter reply link for the deputy's latest tweet"""
        if not self.latest_tweet_url:
            return None
            
        import re
        from urllib.parse import quote
        
        # Extract tweet ID
        tweet_id_match = re.search(r'/status/(\d+)', self.latest_tweet_url)
        if not tweet_id_match:
            return None
            
        tweet_id = tweet_id_match.group(1)
        
        # Default message
        if not message:
            message = f"Olá {self.nome_parlamentar}! Gostaria de dialogar sobre suas propostas. #TransparênciaPolítica"
        
        encoded_message = quote(message)
        return f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}&text={encoded_message}"
    
    def get_tweets(self):
        """Get all tweets for this deputy ordered by position"""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self)
        return Tweet.objects.filter(content_type=ct, object_id=self.id, is_active=True).order_by('position')
    
    def get_latest_tweet(self):
        """Get the latest tweet (position 1) for this deputy"""
        tweets = self.get_tweets()
        return tweets.filter(position=1).first() if tweets else None
    
    def update_tweets(self, tweet_data):
        """Update the 5 latest tweets for this deputy"""
        from django.contrib.contenttypes.models import ContentType
        import re
        
        ct = ContentType.objects.get_for_model(self)
        
        # Clear existing tweets
        Tweet.objects.filter(content_type=ct, object_id=self.id).delete()
        
        # Handle both list of URLs and list of dictionaries
        if not tweet_data:
            return
            
        # Add new tweets
        for position, tweet_item in enumerate(tweet_data[:5], 1):
            # Handle different input formats
            if isinstance(tweet_item, dict):
                # Dictionary format from Google search
                tweet_url = tweet_item.get('url', '')
                content = tweet_item.get('text', '')
            else:
                # String format (legacy)
                tweet_url = str(tweet_item)
                content = ''
            
            if not tweet_url:
                continue
                
            # Extract tweet ID from URL
            tweet_id_match = re.search(r'/status/(\d+)', tweet_url)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else str(position)
            
            Tweet.objects.create(
                content_type=ct,
                object_id=self.id,
                tweet_url=tweet_url,
                tweet_id=tweet_id,
                tweet_text=content,
                position=position
            )
        
        # Update latest_tweet_url with the first tweet
        if tweet_data:
            first_tweet = tweet_data[0]
            if isinstance(first_tweet, dict):
                self.latest_tweet_url = first_tweet.get('url', '')
            else:
                self.latest_tweet_url = str(first_tweet)
            self.save(update_fields=['latest_tweet_url'])


class Senador(models.Model):
    """
    Simplified model for Brazilian senators (active congressmen only)
    Stores only essential contact and political information
    """
    # Political Identity (required)
    nome_parlamentar = models.CharField(max_length=255, verbose_name="Nome Parlamentar")
    partido = models.CharField(max_length=50, verbose_name="Partido")
    uf = models.CharField(max_length=2, verbose_name="Estado (UF)")
    
    # Contact Information
    email = models.EmailField(null=True, blank=True, verbose_name="Email")
    telefone = models.CharField(max_length=50, null=True, blank=True, verbose_name="Telefone")
    foto_url = models.URLField(null=True, blank=True, verbose_name="Foto")
    
    # Twitter-only Social Media
    twitter_url = models.URLField(null=True, blank=True, verbose_name="Twitter/X")
    
    # Latest Tweet Information
    latest_tweet_url = models.URLField(null=True, blank=True, verbose_name="Último Tweet")
    
    # Social Media Source Tracking
    SOCIAL_MEDIA_SOURCE_CHOICES = [
        ('official_api', 'API Oficial'),
        ('senate_website', 'Site do Senado'),
        ('grok_api', 'Grok API'),
        ('google_search', 'Google Search'),
        ('manual', 'Manual'),
    ]
    
    SOCIAL_MEDIA_CONFIDENCE_CHOICES = [
        ('high', 'Alta'),
        ('medium', 'Média'),
        ('low', 'Baixa'),
    ]
    
    social_media_source = models.CharField(
        max_length=50, null=True, blank=True, 
        choices=SOCIAL_MEDIA_SOURCE_CHOICES,
        verbose_name="Fonte das Redes Sociais",
        help_text="Fonte de onde foi extraída a informação das redes sociais"
    )
    social_media_confidence = models.CharField(
        max_length=20, null=True, blank=True,
        choices=SOCIAL_MEDIA_CONFIDENCE_CHOICES,
        verbose_name="Confiança das Redes Sociais", 
        help_text="Nível de confiança da informação das redes sociais"
    )
    needs_social_media_review = models.BooleanField(
        default=False, verbose_name="Precisa Revisar Redes Sociais"
    )
    
    # System fields (for API integration)
    api_id = models.IntegerField(unique=True, verbose_name="ID na API do Senado")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Senador"
        verbose_name_plural = "Senadores"
        ordering = ['nome_parlamentar']
        indexes = [
            models.Index(fields=['partido']),
            models.Index(fields=['uf']),
            models.Index(fields=['nome_parlamentar']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.nome_parlamentar} ({self.partido}/{self.uf})"
    
    @property
    def has_twitter(self):
        """Check if senator has Twitter account"""
        return bool(self.twitter_url)
    
    @property
    def has_social_media(self):
        """Alias for has_twitter for template compatibility"""
        return self.has_twitter
    
    def get_twitter_reply_link(self, message=None):
        """Generate a Twitter reply link for the senator's latest tweet"""
        if not self.latest_tweet_url:
            return None
            
        import re
        from urllib.parse import quote
        
        # Extract tweet ID
        tweet_id_match = re.search(r'/status/(\d+)', self.latest_tweet_url)
        if not tweet_id_match:
            return None
            
        tweet_id = tweet_id_match.group(1)
        
        # Default message
        if not message:
            message = f"Olá {self.nome_parlamentar}! Gostaria de dialogar sobre suas propostas. #TransparênciaPolítica"
        
        encoded_message = quote(message)
        return f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}&text={encoded_message}"
    
    def get_tweets(self):
        """Get all tweets for this senator ordered by position"""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self)
        return Tweet.objects.filter(content_type=ct, object_id=self.id, is_active=True).order_by('position')
    
    def get_latest_tweet(self):
        """Get the latest tweet (position 1) for this senator"""
        tweets = self.get_tweets()
        return tweets.filter(position=1).first() if tweets else None
    
    def update_tweets(self, tweet_data):
        """Update the 5 latest tweets for this senator"""
        from django.contrib.contenttypes.models import ContentType
        import re
        
        ct = ContentType.objects.get_for_model(self)
        
        # Clear existing tweets
        Tweet.objects.filter(content_type=ct, object_id=self.id).delete()
        
        # Handle both list of URLs and list of dictionaries
        if not tweet_data:
            return
            
        # Add new tweets
        for position, tweet_item in enumerate(tweet_data[:5], 1):
            # Handle different input formats
            if isinstance(tweet_item, dict):
                # Dictionary format from Google search
                tweet_url = tweet_item.get('url', '')
                content = tweet_item.get('text', '')
            else:
                # String format (legacy)
                tweet_url = str(tweet_item)
                content = ''
            
            if not tweet_url:
                continue
                
            # Extract tweet ID from URL
            tweet_id_match = re.search(r'/status/(\d+)', tweet_url)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else str(position)
            
            Tweet.objects.create(
                content_type=ct,
                object_id=self.id,
                tweet_url=tweet_url,
                tweet_id=tweet_id,
                tweet_text=content,
                position=position
            )
        
        # Update latest_tweet_url with the first tweet
        if tweet_data:
            first_tweet = tweet_data[0]
            if isinstance(first_tweet, dict):
                self.latest_tweet_url = first_tweet.get('url', '')
            else:
                self.latest_tweet_url = str(first_tweet)
            self.save(update_fields=['latest_tweet_url'])
