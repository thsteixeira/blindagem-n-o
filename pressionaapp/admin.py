from django.contrib import admin
from .models import Deputado, Senador, TwitterMessage, Tweet

@admin.register(TwitterMessage)
class TwitterMessageAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category', 'priority', 'status', 
        'character_count', 'for_deputies', 'for_senators',
        'times_used', 'created_at'
    ]
    list_filter = [
        'category', 'priority', 'status', 'for_deputies', 'for_senators',
        'created_at', 'created_by'
    ]
    search_fields = [
        'title', 'message', 'hashtags', 'mentions'
    ]
    readonly_fields = [
        'character_count', 'remaining_characters', 'times_used', 
        'last_used_at', 'created_at', 'updated_at', 'sent_at'
    ]
    
    fieldsets = (
        ('Conteúdo da Mensagem', {
            'fields': (
                'title', 'message', 'category', 'priority'
            )
        }),
        ('Elementos do Twitter', {
            'fields': (
                'hashtags', 'mentions'
            )
        }),
        ('Público Alvo', {
            'fields': (
                'for_deputies', 'for_senators', 'target_parties', 'target_states'
            )
        }),
        ('Status e Agendamento', {
            'fields': (
                'status', 'scheduled_for'
            )
        }),
        ('Estatísticas de Uso', {
            'fields': (
                'character_count', 'remaining_characters', 'times_used', 'last_used_at'
            ),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': (
                'created_by', 'created_at', 'updated_at', 'sent_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def character_count(self, obj):
        return obj.character_count
    character_count.short_description = 'Caracteres'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Tweet)
class TweetAdmin(admin.ModelAdmin):
    list_display = [
        'get_parliamentarian_name', 'get_parliamentarian_type', 'position', 
        'tweet_url', 'has_content', 'discovered_at'
    ]
    list_filter = [
        'content_type', 'position', 'discovered_at', 'is_active'
    ]
    search_fields = [
        'tweet_url', 'tweet_text', 'tweet_id'
    ]
    readonly_fields = [
        'discovered_at', 'tweet_id'
    ]
    
    fieldsets = (
        ('Tweet Info', {
            'fields': (
                'content_type', 'object_id', 'position'
            )
        }),
        ('Tweet Content', {
            'fields': (
                'tweet_url', 'tweet_id', 'tweet_text', 'tweet_date'
            )
        }),
        ('Status', {
            'fields': (
                'is_active', 'needs_content_update'
            )
        }),
        ('Metadata', {
            'fields': (
                'discovered_at',
            ),
            'classes': ('collapse',)
        })
    )
    
    def get_parliamentarian_name(self, obj):
        if obj.parliamentarian:
            return obj.parliamentarian.nome_parlamentar
        return "N/A"
    get_parliamentarian_name.short_description = 'Parlamentar'
    
    def get_parliamentarian_type(self, obj):
        if obj.content_type:
            return obj.content_type.model.title()
        return "N/A"
    get_parliamentarian_type.short_description = 'Tipo'
    get_parliamentarian_type.admin_order_field = 'content_type__model'
    
    def has_content(self, obj):
        return bool(obj.tweet_text and obj.tweet_text.strip())
    has_content.boolean = True
    has_content.short_description = 'Tem Conteúdo'


@admin.register(Deputado)
class DeputadoAdmin(admin.ModelAdmin):
    list_display = [
        'nome_parlamentar', 'has_twitter', 'partido', 'uf',
        'latest_tweet_link', 'tweet_count',
        'social_media_source', 'social_media_confidence', 'needs_social_media_review', 'is_active'
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
        ('Twitter', {
            'fields': (
                'twitter_url', 'latest_tweet_url'
            )
        }),
        ('Dados de Redes Sociais (Grok AI)', {
            'fields': (
                'social_media_source', 'social_media_confidence', 
                'needs_social_media_review'
            ),
            'description': 'Informações extraídas via API oficial, scraping do site ou Grok AI',
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def has_twitter(self, obj):
        if obj.twitter_url:
            from django.utils.html import format_html
            import re
            
            # Extract username from Twitter/X URL using regex
            # Handle both twitter.com and x.com, with or without @ in URL
            pattern = r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(?:@)?(\w+)(?:\?.*)?'
            match = re.match(pattern, obj.twitter_url)
            
            if match:
                username = match.group(1)
                return format_html(
                    '<a href="{}" target="_blank">@{}</a>',
                    obj.twitter_url,
                    username
                )
            else:
                # Fallback: just show the URL if pattern doesn't match
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    obj.twitter_url,
                    obj.twitter_url
                )
        return '-'
    has_twitter.short_description = 'Twitter'
    has_twitter.allow_tags = True
    
    def latest_tweet_link(self, obj):
        if obj.latest_tweet_url:
            from django.utils.html import format_html
            import re
            
            # Extract tweet ID from URL for display
            tweet_id_match = re.search(r'/status/(\d+)', obj.latest_tweet_url)
            if tweet_id_match:
                tweet_id = tweet_id_match.group(1)
                # Show short tweet ID as clickable link
                return format_html(
                    '<a href="{}" target="_blank">Tweet #{}</a>',
                    obj.latest_tweet_url,
                    tweet_id[-6:]  # Last 6 digits of tweet ID
                )
            else:
                # Fallback: show "Tweet" if URL doesn't match pattern
                return format_html(
                    '<a href="{}" target="_blank">Tweet</a>',
                    obj.latest_tweet_url
                )
        # Show red X when no latest tweet
        from django.utils.html import format_html
        return format_html('<span style="color: red; font-weight: bold;">✗</span>')
    latest_tweet_link.short_description = 'Último Tweet'
    latest_tweet_link.allow_tags = True
    
    def tweet_count(self, obj):
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(obj)
        return Tweet.objects.filter(content_type=content_type, object_id=obj.id).count()
    tweet_count.short_description = 'Tweets'
    
    def get_tweets_display(self, obj):
        from django.contrib.contenttypes.models import ContentType
        from django.utils.html import format_html
        
        content_type = ContentType.objects.get_for_model(obj)
        tweets = Tweet.objects.filter(content_type=content_type, object_id=obj.id).order_by('position')
        
        if not tweets:
            return "Nenhum tweet encontrado"
        
        tweet_links = []
        for tweet in tweets:
            tweet_links.append(
                f'<a href="{tweet.tweet_url}" target="_blank">Tweet {tweet.position}</a>'
            )
        
        return format_html('<br>'.join(tweet_links))
    get_tweets_display.short_description = 'Tweets'
    get_tweets_display.allow_tags = True
    
    actions = ['mark_for_social_media_review', 'clear_social_media_review_flag']
    
    def mark_for_social_media_review(self, request, queryset):
        """Mark selected deputies for social media review"""
        updated = queryset.update(needs_social_media_review=True)
        self.message_user(
            request, 
            f'{updated} deputado(s) marcado(s) para revisão de redes sociais.'
        )
    mark_for_social_media_review.short_description = 'Marcar para revisão de redes sociais'
    
    def clear_social_media_review_flag(self, request, queryset):
        """Remove selected deputies from social media review"""
        updated = queryset.update(needs_social_media_review=False)
        self.message_user(
            request, 
            f'{updated} deputado(s) removido(s) da revisão de redes sociais.'
        )
    clear_social_media_review_flag.short_description = 'Remover da revisão de redes sociais'


@admin.register(Senador)
class SenadorAdmin(admin.ModelAdmin):
    list_display = [
        'nome_parlamentar', 'has_twitter', 'partido', 'uf',
        'latest_tweet_link', 'tweet_count',
        'social_media_source', 'social_media_confidence', 'needs_social_media_review', 'is_active'
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
        ('Twitter', {
            'fields': (
                'twitter_url', 'latest_tweet_url'
            )
        }),
        ('Dados de Redes Sociais (Grok AI)', {
            'fields': (
                'social_media_source', 'social_media_confidence', 
                'needs_social_media_review'
            ),
            'description': 'Informações extraídas via API oficial, scraping do site ou Grok AI',
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def has_twitter(self, obj):
        if obj.twitter_url:
            from django.utils.html import format_html
            import re
            
            # Extract username from Twitter/X URL using regex
            # Handle both twitter.com and x.com, with or without @ in URL
            pattern = r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(?:@)?(\w+)(?:\?.*)?'
            match = re.match(pattern, obj.twitter_url)
            
            if match:
                username = match.group(1)
                return format_html(
                    '<a href="{}" target="_blank">@{}</a>',
                    obj.twitter_url,
                    username
                )
            else:
                # Fallback: just show the URL if pattern doesn't match
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    obj.twitter_url,
                    obj.twitter_url
                )
        return '-'
    has_twitter.short_description = 'Twitter'
    has_twitter.allow_tags = True
    
    def latest_tweet_link(self, obj):
        if obj.latest_tweet_url:
            from django.utils.html import format_html
            import re
            
            # Extract tweet ID from URL for display
            tweet_id_match = re.search(r'/status/(\d+)', obj.latest_tweet_url)
            if tweet_id_match:
                tweet_id = tweet_id_match.group(1)
                # Show short tweet ID as clickable link
                return format_html(
                    '<a href="{}" target="_blank">Tweet #{}</a>',
                    obj.latest_tweet_url,
                    tweet_id[-6:]  # Last 6 digits of tweet ID
                )
            else:
                # Fallback: show "Tweet" if URL doesn't match pattern
                return format_html(
                    '<a href="{}" target="_blank">Tweet</a>',
                    obj.latest_tweet_url
                )
        # Show red X when no latest tweet
        from django.utils.html import format_html
        return format_html('<span style="color: red; font-weight: bold;">✗</span>')
    latest_tweet_link.short_description = 'Último Tweet'
    latest_tweet_link.allow_tags = True
    
    def tweet_count(self, obj):
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(obj)
        return Tweet.objects.filter(content_type=content_type, object_id=obj.id).count()
    tweet_count.short_description = 'Tweets'
    
    actions = ['mark_for_social_media_review', 'clear_social_media_review_flag']
    
    def mark_for_social_media_review(self, request, queryset):
        """Mark selected senators for social media review"""
        updated = queryset.update(needs_social_media_review=True)
        self.message_user(
            request, 
            f'{updated} senador(es) marcado(s) para revisão de redes sociais.'
        )
    mark_for_social_media_review.short_description = 'Marcar para revisão de redes sociais'
    
    def clear_social_media_review_flag(self, request, queryset):
        """Remove selected senators from social media review"""
        updated = queryset.update(needs_social_media_review=False)
        self.message_user(
            request, 
            f'{updated} senador(es) removido(s) da revisão de redes sociais.'
        )
    clear_social_media_review_flag.short_description = 'Remover da revisão de redes sociais'


# Admin site customization
admin.site.site_header = "Pressiona - Plataforma de Transparência Política"
admin.site.site_title = "Admin Pressiona"
admin.site.index_title = "Gerenciamento da Plataforma com IA Grok"