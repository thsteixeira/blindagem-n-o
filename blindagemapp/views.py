from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Deputado, Senador

# Create your views here.

def home_view(request):
    """View da página inicial com estatísticas gerais"""
    total_deputados = Deputado.objects.filter(is_active=True).count()
    deputados_com_redes_sociais = Deputado.objects.filter(
        is_active=True,
        twitter_url__isnull=False
    ).count()
    
    # Estatísticas dos senadores
    total_senadores = Senador.objects.filter(is_active=True).count()
    senadores_com_redes_sociais = Senador.objects.filter(
        is_active=True,
        twitter_url__isnull=False
    ).count()
    
    context = {
        'total_deputados': total_deputados,
        'deputados_com_redes_sociais': deputados_com_redes_sociais,
        'percentual_com_redes': round((deputados_com_redes_sociais / total_deputados * 100) if total_deputados > 0 else 0, 1),
        'total_senadores': total_senadores,
        'senadores_com_redes_sociais': senadores_com_redes_sociais,
        'percentual_senadores_com_redes': round((senadores_com_redes_sociais / total_senadores * 100) if total_senadores > 0 else 0, 1)
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
    deputados = Deputado.objects.filter(is_active=True)
    
    # Aplicar filtros
    if search_query:
        deputados = deputados.filter(
            Q(nome_parlamentar__icontains=search_query)
        )
    
    if partido_filter:
        deputados = deputados.filter(partido=partido_filter)
    
    if uf_filter:
        deputados = deputados.filter(uf=uf_filter)
    
    if has_social_media == 'yes':
        deputados = deputados.filter(twitter_url__isnull=False)
    elif has_social_media == 'no':
        deputados = deputados.filter(twitter_url__isnull=True)
    
    # Ordenação
    deputados = deputados.order_by('nome_parlamentar')
    
    # Paginação
    paginator = Paginator(deputados, 20)  # 20 deputados por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    partidos = Deputado.objects.filter(is_active=True).values_list('partido', flat=True).distinct().order_by('partido')
    ufs = Deputado.objects.filter(is_active=True).values_list('uf', flat=True).distinct().order_by('uf')
    
    # Estatísticas para os cards
    total_deputados = Deputado.objects.filter(is_active=True).count()
    com_redes_sociais = Deputado.objects.filter(is_active=True, twitter_url__isnull=False).count()
    sem_redes_sociais = total_deputados - com_redes_sociais
    percentual_com_redes = round((com_redes_sociais / total_deputados * 100) if total_deputados > 0 else 0, 1)
    percentual_sem_redes = 100 - percentual_com_redes
    total_estados = Deputado.objects.filter(is_active=True).values_list('uf', flat=True).distinct().count()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'partido_filter': partido_filter,
        'uf_filter': uf_filter,
        'has_social_media': has_social_media,
        'partidos': partidos,
        'ufs': ufs,
        'total_deputados': deputados.count(),
        'com_redes_sociais': com_redes_sociais,
        'sem_redes_sociais': sem_redes_sociais,
        'percentual_com_redes': percentual_com_redes,
        'percentual_sem_redes': percentual_sem_redes,
        'total_estados': total_estados
    }
    
    return render(request, 'blindagemapp/deputados_list.html', context)

def deputado_detail_view(request, deputado_id):
    """View para detalhes de um deputado específico"""
    deputado = get_object_or_404(Deputado, api_id=deputado_id, is_active=True)
    
    # Verificar se tem Twitter
    social_media_count = 1 if deputado.twitter_url else 0
    
    context = {
        'deputado': deputado,
        'social_media_count': social_media_count
    }
    
    return render(request, 'blindagemapp/deputado_detail.html', context)


def senadores_list_view(request):
    """View para listar todos os senadores com paginação e filtros"""
    # Filtros
    search_query = request.GET.get('search', '')
    partido_filter = request.GET.get('partido', '')
    uf_filter = request.GET.get('uf', '')
    has_social_media = request.GET.get('has_social_media', '')
    
    # Query base
    senadores = Senador.objects.filter(is_active=True)
    
    # Aplicar filtros
    if search_query:
        senadores = senadores.filter(
            Q(nome_parlamentar__icontains=search_query)
        )
    
    if partido_filter:
        senadores = senadores.filter(partido=partido_filter)
    
    if uf_filter:
        senadores = senadores.filter(uf=uf_filter)
    
    if has_social_media == 'yes':
        senadores = senadores.filter(twitter_url__isnull=False)
    elif has_social_media == 'no':
        senadores = senadores.filter(twitter_url__isnull=True)
    
    # Ordenação
    senadores = senadores.order_by('nome_parlamentar')
    
    # Paginação
    paginator = Paginator(senadores, 20)  # 20 senadores por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    partidos = Senador.objects.filter(is_active=True).values_list('partido', flat=True).distinct().order_by('partido')
    ufs = Senador.objects.filter(is_active=True).values_list('uf', flat=True).distinct().order_by('uf')
    
    # Estatísticas para os cards
    total_senadores = Senador.objects.filter(is_active=True).count()
    com_redes_sociais = Senador.objects.filter(is_active=True, twitter_url__isnull=False).count()
    sem_redes_sociais = total_senadores - com_redes_sociais
    percentual_com_redes = round((com_redes_sociais / total_senadores * 100) if total_senadores > 0 else 0, 1)
    percentual_sem_redes = 100 - percentual_com_redes
    total_estados = Senador.objects.filter(is_active=True).values_list('uf', flat=True).distinct().count()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'partido_filter': partido_filter,
        'uf_filter': uf_filter,
        'has_social_media': has_social_media,
        'partidos': partidos,
        'ufs': ufs,
        'total_senadores': senadores.count(),
        'com_redes_sociais': com_redes_sociais,
        'sem_redes_sociais': sem_redes_sociais,
        'percentual_com_redes': percentual_com_redes,
        'percentual_sem_redes': percentual_sem_redes,
        'total_estados': total_estados
    }
    
    return render(request, 'blindagemapp/senadores_list.html', context)


def senador_detail_view(request, senador_id):
    """View para detalhes de um senador específico"""
    senador = get_object_or_404(Senador, api_id=senador_id, is_active=True)
    
    # Verificar se tem Twitter
    social_media_count = 1 if senador.twitter_url else 0
    
    context = {
        'senador': senador,
        'social_media_count': social_media_count
    }
    
    return render(request, 'blindagemapp/senador_detail.html', context)
