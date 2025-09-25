from django.db import models


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
    social_media_source = models.CharField(
        max_length=50, null=True, blank=True, 
        verbose_name="Fonte das Redes Sociais",
        help_text="chamber_website, google_search, or manual"
    )
    social_media_confidence = models.CharField(
        max_length=20, null=True, blank=True,
        verbose_name="Confiança das Redes Sociais", 
        help_text="high, medium, low"
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
    social_media_source = models.CharField(
        max_length=50, null=True, blank=True, 
        verbose_name="Fonte das Redes Sociais",
        help_text="chamber_website, google_search, or manual"
    )
    social_media_confidence = models.CharField(
        max_length=20, null=True, blank=True,
        verbose_name="Confiança das Redes Sociais", 
        help_text="high, medium, low"
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
