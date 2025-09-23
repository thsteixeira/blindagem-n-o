from django.contrib import admin
from .models import Deputado, Senador

@admin.register(Deputado)
class DeputadoAdmin(admin.ModelAdmin):
    list_display = [
        'nome_parlamentar', 'partido', 'uf',
        'has_facebook', 'has_twitter', 'has_instagram',
        'social_media_confidence', 'needs_social_media_review', 'is_active'
    ]
    list_filter = [
        'partido', 'uf', 'is_active', 'social_media_confidence', 
        'needs_social_media_review', 'social_media_source', 'created_at'
    ]
    search_fields = [
        'nome_parlamentar', 'partido', 'uf', 'email'
    ]
    readonly_fields = [
        'api_id', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'nome_parlamentar', 'api_id', 'is_active'
            )
        }),
        ('Informações Políticas', {
            'fields': (
                'partido', 'uf'
            )
        }),
        ('Contato', {
            'fields': (
                'email', 'telefone', 'foto_url'
            )
        }),
        ('Redes Sociais', {
            'fields': (
                'facebook_url', 'twitter_url', 'instagram_url',
                'youtube_url', 'tiktok_url', 'linkedin_url'
            )
        }),
        ('Confiança das Redes Sociais', {
            'fields': (
                'social_media_source', 'social_media_confidence', 
                'needs_social_media_review'
            ),
            'classes': ('collapse',)
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


@admin.register(Senador)
class SenadorAdmin(admin.ModelAdmin):
    list_display = [
        'nome_parlamentar', 'partido', 'uf',
        'has_facebook', 'has_twitter', 'has_instagram',
        'social_media_confidence', 'needs_social_media_review', 'is_active'
    ]
    list_filter = [
        'partido', 'uf', 'is_active', 'social_media_confidence', 
        'needs_social_media_review', 'social_media_source', 'created_at'
    ]
    search_fields = [
        'nome_parlamentar', 'partido', 'uf', 'email'
    ]
    readonly_fields = [
        'api_id', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'nome_parlamentar', 'api_id', 'is_active'
            )
        }),
        ('Informações Políticas', {
            'fields': (
                'partido', 'uf'
            )
        }),
        ('Contato', {
            'fields': (
                'email', 'telefone', 'foto_url'
            )
        }),
        ('Redes Sociais', {
            'fields': (
                'facebook_url', 'twitter_url', 'instagram_url',
                'youtube_url', 'tiktok_url', 'linkedin_url'
            )
        }),
        ('Confiança das Redes Sociais', {
            'fields': (
                'social_media_source', 'social_media_confidence', 
                'needs_social_media_review'
            ),
            'classes': ('collapse',)
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