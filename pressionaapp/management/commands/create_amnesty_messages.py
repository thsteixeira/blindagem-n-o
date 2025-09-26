from django.core.management.base import BaseCommand
from pressionaapp.models import TwitterMessage


class Command(BaseCommand):
    help = 'Create Twitter messages against amnesty projects in Brazil'

    def handle(self, *args, **options):
        messages = [
            {
                'title': 'Contra Anistia - Justiça',
                'message': 'Deputado/Senador, o povo brasileiro não aceita anistia para corruptos! Precisamos de justiça, não de impunidade. Vote CONTRA qualquer projeto de anistia!',
                'category': 'criticism',
                'priority': 'high',
                'hashtags': '#SemAnistia #JustiçaJá #ContraCorrupção #TransparênciaPolítica',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Anistia é Impunidade',
                'message': 'Anistia = impunidade! O Brasil precisa de políticos que defendam a justiça, não que protejam corruptos. Qual sua posição sobre os projetos de anistia?',
                'category': 'question',
                'priority': 'high',
                'hashtags': '#AnistiaÉImpunidade #JustiçaSocial #VoteContra',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Prestação de Contas',
                'message': 'Seus eleitores querem saber: você vai votar A FAVOR ou CONTRA projetos de anistia? O povo tem direito à transparência na sua decisão!',
                'category': 'question',
                'priority': 'medium',
                'hashtags': '#PrestaçãoDeContas #TransparênciaTotal #ResponsabilidadePolítica',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Representatividade Popular',
                'message': 'Pesquisas mostram que a maioria dos brasileiros é CONTRA anistia. Como nosso representante, você deve votar conforme a vontade popular!',
                'category': 'opinion',
                'priority': 'medium',
                'hashtags': '#VontadePopular #RepresentaçãoDemocrática #ContraAnistia',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Combate à Corrupção',
                'message': 'O combate à corrupção não pode retroceder! Anistia é um sinal verde para a impunidade. Defend[a a Lei e a Ordem! #CombateCorrupção',
                'category': 'criticism',
                'priority': 'high',
                'hashtags': '#CombateCorrupção #LeiEOrdem #NãoÀImpunidade #JustiçaBrasil',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Confiança Institucional',
                'message': 'Projetos de anistia destroem a confiança do povo nas instituições! Como parlamentar, você deve fortalecer, não enfraquecer nossa democracia.',
                'category': 'criticism',
                'priority': 'medium',
                'hashtags': '#ConfiançaInstitucional #FortalecerDemocracia #ContraAnistia',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Ética na Política',
                'message': 'Ética na política não é negociável! Votar por anistia é compactuar com a corrupção. O Brasil merece representantes íntegros!',
                'category': 'criticism',
                'priority': 'medium',
                'hashtags': '#ÉticaNaPolítica #IntegridadePública #VotaContraAnistia',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Recursos Públicos',
                'message': 'Cada real desviado por corruptos sai da saúde, educação e segurança do povo! Não permita que anistia proteja quem rouba o Brasil!',
                'category': 'criticism',
                'priority': 'high',
                'hashtags': '#RecursosPúblicos #SaúdeEducaçãoSegurança #ContraRoubo #SemAnistia',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Compromisso Eleitoral',
                'message': 'Durante a campanha você prometeu combater a corrupção. Cumpra sua palavra: vote CONTRA qualquer projeto de anistia!',
                'category': 'opinion',
                'priority': 'medium',
                'hashtags': '#CumpraSuaPalavra #CompromissoEleitoral #ContraCorrupção',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Futuro do Brasil',
                'message': 'O futuro do Brasil depende de justiça, não de impunidade! Seja parte da solução: vote contra anistia e a favor da moralidade!',
                'category': 'opinion',
                'priority': 'medium',
                'hashtags': '#FuturoDoBrasil #JustiçaEMoralidade #ContraImpunidade',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Cobrança Direta - PEC da Anistia',
                'message': 'A PEC da Anistia é um retrocesso! Como você justifica proteger quem cometeu crimes contra o erário público? O povo quer explicações!',
                'category': 'question',
                'priority': 'urgent',
                'hashtags': '#PECdaAnistia #CrimesContraErário #QueryJustificativa #Retrocesso',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Multas Eleitorais - Anistia',
                'message': 'Anistiar multas eleitorais incentiva desrespeito às leis! Quem não cumpre regras eleitorais não deveria estar no poder. Posicione-se!',
                'category': 'criticism',
                'priority': 'high',
                'hashtags': '#MultasEleitorais #DesrespeitoÀsLeis #RegrasDemocráticas',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Mensagem Direta - Posicionamento',
                'message': 'Deputado/Senador, sua posição sobre anistia define se você está do lado do povo ou dos corruptos. Em qual lado você está?',
                'category': 'question',
                'priority': 'high',
                'hashtags': '#DefinaSeuLado #PopulouCorruptos #PosiçãoClara',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Responsabilização Criminal',
                'message': 'Crimes devem ser punidos, não anistiados! O Brasil precisa de parlamentares que defendam a responsabilização criminal efetiva!',
                'category': 'criticism',
                'priority': 'high',
                'hashtags': '#ResponsabilizaçãoCriminal #CrimesDevemSerPunidos #JustiçaEfetiva',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            },
            {
                'title': 'Exemplo para Sociedade',
                'message': 'Que exemplo estamos dando para nossos filhos se criminosos ficam impunes? Vote contra anistia e a favor de uma sociedade justa!',
                'category': 'opinion',
                'priority': 'medium',
                'hashtags': '#ExemploParaSociedade #SociedadeJusta #EducaçãoCívica',
                'for_deputies': True,
                'for_senators': True,
                'status': 'ready'
            }
        ]

        created_count = 0
        
        for message_data in messages:
            message, created = TwitterMessage.objects.get_or_create(
                title=message_data['title'],
                defaults=message_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Criada mensagem: "{message.title}"')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Mensagem já existe: "{message.title}"')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído! {created_count} novas mensagens contra anistia foram criadas.'
            )
        )
        self.stdout.write(
            'Acesse o admin Django em /admin/ para gerenciar as mensagens.'
        )