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
    
    # Social Media Links
    facebook_url = models.URLField(null=True, blank=True, verbose_name="Facebook")
    twitter_url = models.URLField(null=True, blank=True, verbose_name="Twitter/X")
    instagram_url = models.URLField(null=True, blank=True, verbose_name="Instagram") 
    youtube_url = models.URLField(null=True, blank=True, verbose_name="YouTube")
    tiktok_url = models.URLField(null=True, blank=True, verbose_name="TikTok")
    linkedin_url = models.URLField(null=True, blank=True, verbose_name="LinkedIn")
    
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
    def has_social_media(self):
        """Check if deputy has any social media links"""
        return any([
            self.facebook_url,
            self.twitter_url, 
            self.instagram_url,
            self.youtube_url,
            self.tiktok_url,
            self.linkedin_url
        ])


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
    
    # Social Media Links
    facebook_url = models.URLField(null=True, blank=True, verbose_name="Facebook")
    twitter_url = models.URLField(null=True, blank=True, verbose_name="Twitter/X")
    instagram_url = models.URLField(null=True, blank=True, verbose_name="Instagram")
    youtube_url = models.URLField(null=True, blank=True, verbose_name="YouTube")
    tiktok_url = models.URLField(null=True, blank=True, verbose_name="TikTok")
    linkedin_url = models.URLField(null=True, blank=True, verbose_name="LinkedIn")
    
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
    def has_social_media(self):
        """Check if senator has any social media links"""
        return any([
            self.facebook_url,
            self.twitter_url,
            self.instagram_url,
            self.youtube_url,
            self.tiktok_url,
            self.linkedin_url
        ])
