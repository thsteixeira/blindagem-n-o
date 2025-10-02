from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
from .models import Deputado, Senador, TwitterMessage
from .turnstile_utils import verify_turnstile_token, get_client_ip, mark_turnstile_verified

logger = logging.getLogger(__name__)

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
    return render(request, 'pressionaapp/home.html', context)

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
    
    return render(request, 'pressionaapp/deputados_list.html', context)

def deputado_detail_view(request, deputado_id):
    """View para detalhes de um deputado específico"""
    deputado = get_object_or_404(Deputado, api_id=deputado_id, is_active=True)
    
    # Verificar se tem Twitter
    social_media_count = 1 if deputado.twitter_url else 0
    
    context = {
        'deputado': deputado,
        'social_media_count': social_media_count
    }
    
    return render(request, 'pressionaapp/deputado_detail.html', context)


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
    
    return render(request, 'pressionaapp/senadores_list.html', context)


def senador_detail_view(request, senador_id):
    """View para detalhes de um senador específico"""
    senador = get_object_or_404(Senador, api_id=senador_id, is_active=True)
    
    # Verificar se tem Twitter
    social_media_count = 1 if senador.twitter_url else 0
    
    context = {
        'senador': senador,
        'social_media_count': social_media_count
    }
    
    return render(request, 'pressionaapp/senador_detail.html', context)


def twitter_messages_list_view(request):
    """Enhanced view to list Twitter messages with filtering and pagination"""
    # Filters
    status_filter = request.GET.get('status', 'ready')
    category_filter = request.GET.get('category', '')
    priority_filter = request.GET.get('priority', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    messages = TwitterMessage.objects.all()
    
    # Apply filters
    if status_filter:
        messages = messages.filter(status=status_filter)
    
    if category_filter:
        messages = messages.filter(category=category_filter)
    
    if priority_filter:
        messages = messages.filter(priority=priority_filter)
    
    if search_query:
        messages = messages.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    # Ordering
    messages = messages.order_by('priority', '-created_at')
    
    # Pagination
    paginator = Paginator(messages, 12)  # 12 messages per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Filter options for dropdowns
    categories = TwitterMessage.CATEGORY_CHOICES
    priorities = TwitterMessage.PRIORITY_CHOICES
    statuses = TwitterMessage.STATUS_CHOICES
    
    # Statistics
    total_messages = TwitterMessage.objects.count()
    ready_messages = TwitterMessage.objects.filter(status='ready').count()
    draft_messages = TwitterMessage.objects.filter(status='draft').count()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'priority_filter': priority_filter,
        'categories': categories,
        'priorities': priorities,
        'statuses': statuses,
        'total_messages': total_messages,
        'ready_messages': ready_messages,
        'draft_messages': draft_messages,
        'filtered_count': messages.count(),
    }
    
    return render(request, 'pressionaapp/twitter_messages_list.html', context)


@require_POST
def mark_message_used(request, message_id):
    """Mark a Twitter message as used"""
    message = get_object_or_404(TwitterMessage, id=message_id)
    message.mark_as_used()
    return JsonResponse({'status': 'success', 'times_used': message.times_used})


def twitter_message_preview(request, message_id):
    """Preview how a Twitter message will look"""
    message = get_object_or_404(TwitterMessage, id=message_id)
    
    # Get sample parliamentarians for preview
    sample_deputy = Deputado.objects.filter(is_active=True, twitter_url__isnull=False).first()
    sample_senator = Senador.objects.filter(is_active=True, twitter_url__isnull=False).first()
    
    previews = []
    
    if sample_deputy and message.for_deputies:
        twitter_handle = sample_deputy.twitter_url.split('/')[-1] if sample_deputy.twitter_url else None
        formatted_message = message.get_formatted_message(twitter_handle)
        previews.append({
            'type': 'Deputado',
            'name': sample_deputy.nome_parlamentar,
            'message': formatted_message,
            'character_count': len(formatted_message)
        })
    
    if sample_senator and message.for_senators:
        twitter_handle = sample_senator.twitter_url.split('/')[-1] if sample_senator.twitter_url else None
        formatted_message = message.get_formatted_message(twitter_handle)
        previews.append({
            'type': 'Senador',
            'name': sample_senator.nome_parlamentar,
            'message': formatted_message,
            'character_count': len(formatted_message)
        })
    
    context = {
        'message': message,
        'previews': previews
    }
    
    return render(request, 'pressionaapp/twitter_message_preview.html', context)


@csrf_exempt
@require_POST
def verify_turnstile_view(request):
    """
    AJAX endpoint to verify Turnstile token
    """
    try:
        # Parse JSON data
        data = json.loads(request.body)
        token = data.get('token')
        
        if not token:
            return JsonResponse({
                'success': False,
                'error': 'Token missing',
                'message': 'Token de verificação não fornecido'
            }, status=400)
        
        # Get client IP
        ip_address = get_client_ip(request)
        
        # Verify token with Cloudflare
        verification_result = verify_turnstile_token(token, ip_address)
        
        if verification_result['success']:
            # Mark session as verified
            mark_turnstile_verified(request)
            
            logger.info(f"Turnstile verification successful for IP: {ip_address}")
            
            return JsonResponse({
                'success': True,
                'message': 'Verificação realizada com sucesso',
                'hostname': verification_result.get('hostname'),
                'challenge_ts': verification_result.get('challenge_ts')
            })
        else:
            logger.warning(f"Turnstile verification failed for IP: {ip_address}, errors: {verification_result.get('error_codes', [])}")
            
            return JsonResponse({
                'success': False,
                'error': 'Verification failed',
                'error_codes': verification_result.get('error_codes', []),
                'message': verification_result.get('message', 'Falha na verificação')
            }, status=403)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
            'message': 'Dados inválidos'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error in Turnstile verification: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal error',
            'message': 'Erro interno do servidor'
        }, status=500)


def turnstile_challenge_view(request):
    """
    View to display Turnstile challenge page
    """
    return render(request, 'pressionaapp/turnstile_challenge.html')
