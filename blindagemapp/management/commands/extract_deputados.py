"""
Comando Django para executar o crawler dos deputados da Câmara
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from blindagemapp.deputados_extractor import DeputadosDataExtractor
from blindagemapp.models import Deputado, HistoricoMandato


class Command(BaseCommand):
    help = 'Executa o extrator de dados para deputados brasileiros (API + web scraping)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--legislatura',
            type=int,
            default=57,
            help='Número da legislatura a ser processada (padrão: 57)'
        )
        
        parser.add_argument(
            '--all-legislaturas',
            action='store_true',
            help='Processar todas as legislaturas disponíveis'
        )
        
        parser.add_argument(
            '--with-details',
            action='store_true',
            default=True,
            help='Obter dados detalhados de cada deputado (padrão: True)'
        )
        
        parser.add_argument(
            '--skip-details',
            action='store_true',
            help='Pular dados detalhados para processamento mais rápido'
        )
        
        parser.add_argument(
            '--skip-social-media',
            action='store_true',
            help='Pular extração de redes sociais (mais rápido)'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Limitar número de deputados processados (útil para testes)'
        )
        
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='Limpar dados existentes antes de executar o crawler'
        )

    def handle(self, *args, **options):
        """
        Executa o comando de crawler
        """
        
        # Limpar dados se solicitado
        if options['clear_data']:
            self.stdout.write(
                self.style.WARNING('Removendo dados existentes...')
            )
            
            with transaction.atomic():
                HistoricoMandato.objects.all().delete()
                Deputado.objects.all().delete()
            
            self.stdout.write(
                self.style.SUCCESS('Dados removidos com sucesso!')
            )
        
        # Configurar extrator
        extractor = DeputadosDataExtractor()
        
        try:
            if options['all_legislaturas']:
                # Processar todas as legislaturas
                self.stdout.write(
                    self.style.NOTICE('Processando todas as legislaturas...')
                )
                
                extractor.extract_all_legislaturas(
                    with_details=not options['skip_details']
                )
                
            else:
                # Processar legislatura específica
                legislatura = options['legislatura']
                
                self.stdout.write(
                    self.style.NOTICE(f'Processando {legislatura}ª legislatura...')
                )
                
                if legislatura == 57:
                    # Usar método específico para 57ª legislatura
                    self.stdout.write('Utilizando método otimizado para 57ª legislatura...')
                    self.stdout.write(f'Extraindo redes sociais: {"Não" if options["skip_social_media"] else "Sim"}')
                    
                    def modified_extract_57(with_details=True, limit=None):
                        return self._extract_with_social_control(
                            extractor, 57, with_details, limit, 
                            not options['skip_social_media']
                        )
                    
                    modified_extract_57(
                        with_details=not options['skip_details'],
                        limit=options['limit']
                    )
                else:
                    # Para outras legislaturas, usar método genérico
                    deputados = extractor.get_deputados_by_legislatura(legislatura)
                    
                    if not deputados:
                        raise CommandError(
                            f'Não foi possível obter dados da {legislatura}ª legislatura'
                        )
                    
                    self.stdout.write(
                        f'Encontrados {len(deputados)} deputados na {legislatura}ª legislatura'
                    )
                    
                    # Aplicar limite se especificado
                    if options['limit']:
                        deputados = deputados[:options['limit']]
                        self.stdout.write(
                            f'Processando apenas os primeiros {options["limit"]} deputados'
                        )
                    
                    processed = 0
                    errors = 0
                    
                    for deputado_data in deputados:
                        try:
                            nome = deputado_data.get('nome', '')
                            id_deputado = deputado_data.get('id')
                            
                            # Obter detalhes se solicitado
                            detalhes = None
                            if not options['skip_details']:
                                detalhes = extractor.get_deputado_detalhes(id_deputado)
                            
                            # Extrair redes sociais se solicitado
                            social_media = None
                            if not options['skip_social_media']:
                                social_media = extractor.extract_social_media_links(id_deputado)
                            
                            # Salvar deputado
                            deputado = extractor.save_deputado(deputado_data, detalhes, social_media)
                            
                            if deputado:
                                # Marcar legislatura
                                deputado.legislatura = str(legislatura)
                                deputado.save()
                                
                                # Obter e salvar mandatos
                                mandatos = extractor.get_deputado_mandatos(id_deputado)
                                if mandatos:
                                    extractor.save_mandatos(deputado, mandatos)
                                
                                processed += 1
                                
                                if processed % 10 == 0:
                                    self.stdout.write(f'Processados: {processed} deputados')
                            else:
                                errors += 1
                            
                            # Pausa para não sobrecarregar a API e site
                            import time
                            sleep_time = 2.0 if not options['skip_social_media'] else 0.5
                            time.sleep(sleep_time)
                            
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Erro ao processar {nome}: {str(e)}')
                            )
                            errors += 1
                            continue
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Processamento concluído! '
                            f'Sucesso: {processed}, Erros: {errors}'
                        )
                    )
            
            # Estatísticas finais
            total_deputados = Deputado.objects.count()
            total_mandatos = HistoricoMandato.objects.count()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\\nEstatísticas finais:'
                    f'\\n- Total de deputados: {total_deputados}'
                    f'\\n- Total de mandatos: {total_mandatos}'
                )
            )
            
            # Mostrar estatísticas por legislatura
            if not options['all_legislaturas']:
                legislatura = options['legislatura']
                deputados_legislatura = Deputado.objects.filter(
                    legislatura=str(legislatura)
                ).count()
                
                self.stdout.write(
                    f'- Deputados da {legislatura}ª legislatura: {deputados_legislatura}'
                )
            
            # Mostrar estatísticas por partido (top 10)
            from django.db.models import Count
            
            partidos = Deputado.objects.values('partido').annotate(
                total=Count('id')
            ).order_by('-total')[:10]
            
            self.stdout.write('\\nTop 10 partidos por número de deputados:')
            for partido in partidos:
                self.stdout.write(
                    f'- {partido["partido"]}: {partido["total"]} deputados'
                )
                
        except Exception as e:
            raise CommandError(f'Erro durante execução do extrator: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS('Extrator de dados executado com sucesso!')
        )
    
    def _extract_with_social_control(self, extractor, legislatura_id, with_details, limit, extract_social_media):
        """
        Método auxiliar para controlar extração de redes sociais
        """
        deputados = extractor.get_deputados_by_legislatura(legislatura_id)
        
        if not deputados:
            raise CommandError(f'Não foi possível obter dados da {legislatura_id}ª legislatura')
        
        self.stdout.write(f'Encontrados {len(deputados)} deputados na {legislatura_id}ª legislatura')
        
        if limit:
            deputados = deputados[:limit]
            self.stdout.write(f'Processando apenas os primeiros {limit} deputados')
        
        processed = 0
        errors = 0
        
        for deputado_data in deputados:
            try:
                # Debug: verificar estrutura dos dados
                if not isinstance(deputado_data, dict):
                    self.stdout.write(
                        self.style.ERROR(f'deputado_data inválido: {type(deputado_data)} - {deputado_data}')
                    )
                    errors += 1
                    continue
                
                nome = deputado_data.get('nome', '')
                id_deputado = deputado_data.get('id')
                
                self.stdout.write(f'Processando {nome} (ID: {id_deputado})...')
                
                # Obter detalhes se solicitado
                detalhes = None
                if with_details:
                    detalhes = extractor.get_deputado_detalhes(id_deputado)
                
                # Extrair redes sociais se solicitado
                social_media = None
                if extract_social_media:
                    self.stdout.write(f'Extraindo redes sociais de {nome}...')
                    social_media = extractor.extract_social_media_links(id_deputado)
                
                # Salvar deputado
                deputado = extractor.save_deputado(deputado_data, detalhes, social_media)
                
                if deputado:
                    # Marcar legislatura
                    deputado.legislatura = str(legislatura_id)
                    deputado.save()
                    
                    # Obter e salvar mandatos
                    mandatos = extractor.get_deputado_mandatos(id_deputado)
                    if mandatos:
                        extractor.save_mandatos(deputado, mandatos)
                    
                    processed += 1
                    
                    if processed % 5 == 0:
                        self.stdout.write(f'Processados: {processed} deputados')
                else:
                    errors += 1
                
                # Pausa maior quando extrai redes sociais
                import time
                sleep_time = 2.0 if extract_social_media else 0.5
                time.sleep(sleep_time)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Erro ao processar {nome}: {str(e)}')
                )
                errors += 1
                continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Processamento concluído! Sucesso: {processed}, Erros: {errors}'
            )
        )