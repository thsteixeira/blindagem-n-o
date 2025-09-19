from django.contrib import admin
from .models import Deputado, HistoricoMandato

@admin.register(Deputado)
class DeputadoAdmin(admin.ModelAdmin):
    list_display = [
        'nome_parlamentar', 'partido', 'uf', 'legislatura',
        'has_facebook', 'has_twitter', 'has_instagram',
        'has_youtube', 'has_tiktok', 'is_active'
    ]
    list_filter = [
        'partido', 'uf', 'legislatura', 'sexo', 'is_active',
        'created_at'
    ]
    search_fields = [
        'nome_parlamentar', 'nome_civil', 'partido', 'uf',
        'email', 'cpf'
    ]
    readonly_fields = [
        'id_deputado_camara', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'nome_parlamentar', 'nome_civil', 'cpf',
                'id_deputado_camara', 'is_active'
            )
        }),
        ('Informações Políticas', {
            'fields': (
                'partido', 'uf', 'legislatura'
            )
        }),
        ('Informações Pessoais', {
            'fields': (
                'sexo', 'data_nascimento', 'naturalidade',
                'profissao', 'escolaridade'
            )
        }),
        ('Contato', {
            'fields': (
                'email', 'telefone', 'site', 'gabinete'
            )
        }),
        ('Redes Sociais', {
            'fields': (
                'facebook_url', 'twitter_url', 'instagram_url',
                'youtube_url', 'tiktok_url', 'linkedin_url'
            )
        }),
        ('Outros', {
            'fields': (
                'biografia', 'foto_url', 'uri_camara'
            )
        }),
        ('Metadados', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def has_facebook(self, obj):
        return bool(obj.facebook_url)
    has_facebook.boolean = True
    has_facebook.short_description = 'Facebook'
    
    def has_twitter(self, obj):
        return bool(obj.twitter_url)
    has_twitter.boolean = True
    has_twitter.short_description = 'Twitter'
    
    def has_instagram(self, obj):
        return bool(obj.instagram_url)
    has_instagram.boolean = True
    has_instagram.short_description = 'Instagram'
    
    def has_youtube(self, obj):
        return bool(obj.youtube_url)
    has_youtube.boolean = True
    has_youtube.short_description = 'YouTube'
    
    def has_tiktok(self, obj):
        return bool(obj.tiktok_url)
    has_tiktok.boolean = True
    has_tiktok.short_description = 'TikTok'

@admin.register(HistoricoMandato)
class HistoricoMandatoAdmin(admin.ModelAdmin):
    list_display = [
        'deputado', 'legislatura', 'data_inicio', 'data_fim',
        'situacao', 'condicao'
    ]
    list_filter = [
        'legislatura', 'situacao', 'condicao', 'data_inicio'
    ]
    search_fields = [
        'deputado__nome_parlamentar', 'deputado__nome_civil',
        'legislatura', 'situacao'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Mandato', {
            'fields': (
                'deputado', 'legislatura', 'data_inicio', 'data_fim'
            )
        }),
        ('Status', {
            'fields': (
                'situacao', 'condicao'
            )
        }),
        ('Metadados', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
