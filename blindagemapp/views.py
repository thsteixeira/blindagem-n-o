from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Deputado

# Create your views here.

def home_view(request):
    """View da página inicial com estatísticas gerais"""
    total_deputados = Deputado.objects.filter(is_active=True).count()
    deputados_com_redes_sociais = Deputado.objects.filter(
        is_active=True
    ).filter(
        Q(facebook_url__isnull=False) | 
        Q(twitter_url__isnull=False) | 
        Q(instagram_url__isnull=False) |
        Q(youtube_url__isnull=False) |
        Q(tiktok_url__isnull=False) |
        Q(linkedin_url__isnull=False)
    ).count()
    
    context = {
        'total_deputados': total_deputados,
        'deputados_com_redes_sociais': deputados_com_redes_sociais,
        'percentual_com_redes': round((deputados_com_redes_sociais / total_deputados * 100) if total_deputados > 0 else 0, 1)
    }
    return render(request, 'blindagemapp/home.html', context)

def deputados_list_view(request):
    """View para listar todos os deputados com paginação e filtros"""
    # Filtros
    search_query = request.GET.get('search', '')
    partido_filter = request.GET.get('partido', '')
    uf_filter = request.GET.get('uf', '')
    has_social_media = request.GET.get('has_social_media', '')
    
    # Query base
    deputados = Deputado.objects.filter(is_active=True, legislatura='57')
    
    # Aplicar filtros
    if search_query:
        deputados = deputados.filter(
            Q(nome_parlamentar__icontains=search_query) |
            Q(nome_civil__icontains=search_query)
        )
    
    if partido_filter:
        deputados = deputados.filter(partido=partido_filter)
    
    if uf_filter:
        deputados = deputados.filter(uf=uf_filter)
    
    if has_social_media == 'yes':
        deputados = deputados.filter(
            Q(facebook_url__isnull=False) | 
            Q(twitter_url__isnull=False) | 
            Q(instagram_url__isnull=False) |
            Q(youtube_url__isnull=False) |
            Q(tiktok_url__isnull=False) |
            Q(linkedin_url__isnull=False)
        )
    elif has_social_media == 'no':
        deputados = deputados.filter(
            facebook_url__isnull=True,
            twitter_url__isnull=True,
            instagram_url__isnull=True,
            youtube_url__isnull=True,
            tiktok_url__isnull=True,
            linkedin_url__isnull=True
        )
    
    # Ordenação
    deputados = deputados.order_by('nome_parlamentar')
    
    # Paginação
    paginator = Paginator(deputados, 20)  # 20 deputados por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    partidos = Deputado.objects.filter(is_active=True, legislatura='57').values_list('partido', flat=True).distinct().order_by('partido')
    ufs = Deputado.objects.filter(is_active=True, legislatura='57').values_list('uf', flat=True).distinct().order_by('uf')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'partido_filter': partido_filter,
        'uf_filter': uf_filter,
        'has_social_media': has_social_media,
        'partidos': partidos,
        'ufs': ufs,
        'total_deputados': deputados.count()
    }
    
    return render(request, 'blindagemapp/deputados_list.html', context)

def deputado_detail_view(request, deputado_id):
    """View para detalhes de um deputado específico"""
    deputado = get_object_or_404(Deputado, id_deputado_camara=deputado_id, is_active=True)
    
    # Contar redes sociais
    social_media_count = sum([
        1 if deputado.facebook_url else 0,
        1 if deputado.twitter_url else 0,
        1 if deputado.instagram_url else 0,
        1 if deputado.youtube_url else 0,
        1 if deputado.tiktok_url else 0,
        1 if deputado.linkedin_url else 0,
    ])
    
    context = {
        'deputado': deputado,
        'social_media_count': social_media_count,
        'mandatos': deputado.historico_mandatos.all().order_by('-data_inicio')
    }
    
    return render(request, 'blindagemapp/deputado_detail.html', context)
