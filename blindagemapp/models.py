from django.db import models
from django.utils import timezone


class Deputado(models.Model):
    """
    Model to store information about Brazilian congressmen (deputados)
    """
    # Basic Information
    nome_civil = models.CharField(max_length=255, verbose_name="Nome Civil")
    nome_parlamentar = models.CharField(max_length=255, verbose_name="Nome Parlamentar")
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    
    # Political Information
    partido = models.CharField(max_length=50, verbose_name="Partido")
    uf = models.CharField(max_length=2, verbose_name="Estado (UF)")
    legislatura = models.CharField(max_length=20, verbose_name="Legislatura")
    
    # Personal Information
    sexo = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Feminino')])
    data_nascimento = models.DateField(null=True, blank=True)
    naturalidade = models.CharField(max_length=255, null=True, blank=True)
    profissao = models.CharField(max_length=255, null=True, blank=True)
    escolaridade = models.CharField(max_length=255, null=True, blank=True)
    
    # Contact Information
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=50, null=True, blank=True)
    site = models.URLField(null=True, blank=True)
    
    # Social Media Links
    facebook_url = models.URLField(null=True, blank=True, verbose_name="Facebook")
    twitter_url = models.URLField(null=True, blank=True, verbose_name="Twitter/X")
    instagram_url = models.URLField(null=True, blank=True, verbose_name="Instagram") 
    youtube_url = models.URLField(null=True, blank=True, verbose_name="YouTube")
    tiktok_url = models.URLField(null=True, blank=True, verbose_name="TikTok")
    linkedin_url = models.URLField(null=True, blank=True, verbose_name="LinkedIn")
    
    # Parliamentary Information
    gabinete = models.CharField(max_length=50, null=True, blank=True)
    comissoes = models.TextField(null=True, blank=True, help_text="Comissões que participa")
    
    # Additional Information
    biografia = models.TextField(null=True, blank=True)
    foto_url = models.URLField(null=True, blank=True)
    
    # System fields
    id_deputado_camara = models.IntegerField(unique=True, null=True, blank=True, 
                                           verbose_name="ID na Câmara")
    uri_camara = models.URLField(null=True, blank=True, verbose_name="URI na API da Câmara")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Deputado"
        verbose_name_plural = "Deputados"
        ordering = ['nome_parlamentar']
        indexes = [
            models.Index(fields=['legislatura', 'partido']),
            models.Index(fields=['uf']),
            models.Index(fields=['nome_parlamentar']),
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


class HistoricoMandato(models.Model):
    """
    Model to store mandate history for deputies
    """
    deputado = models.ForeignKey(Deputado, on_delete=models.CASCADE, related_name='historico_mandatos')
    legislatura = models.CharField(max_length=20)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    situacao = models.CharField(max_length=100)
    condicao = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Histórico de Mandato"
        verbose_name_plural = "Históricos de Mandatos"
        ordering = ['-data_inicio']
    
    def __str__(self):
        return f"{self.deputado.nome_parlamentar} - {self.legislatura}"
