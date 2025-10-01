"""
Django management command to synchronize senator active status with official Senate API
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import requests
import xml.etree.ElementTree as ET
from pressionaapp.models import Senador


class Command(BaseCommand):
    help = 'Synchronize senator active status with official Senate API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making any modifications',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Starting senator status synchronization with official API...")
        
        try:
            # Fetch current senators from official API
            self.stdout.write("📡 Fetching current senators from official Senate API...")
            url = "https://legis.senado.leg.br/dadosabertos/senador/lista/atual"
            
            # Use session with headers to mimic browser requests
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            response = session.get(url)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            senators = root.findall('.//Parlamentar')
            
            # Extract current senator IDs from API
            current_api_ids = set()
            for senator_xml in senators:
                identificacao = senator_xml.find('IdentificacaoParlamentar')
                if identificacao is not None:
                    codigo_parlamentar = self._get_xml_text(identificacao, 'CodigoParlamentar')
                    if codigo_parlamentar:
                        # Ensure consistent string format for comparison
                        current_api_ids.add(str(codigo_parlamentar))
            
            self.stdout.write(f"✅ Found {len(current_api_ids)} active senators in official API")
            
            # Get current database state
            total_senators = Senador.objects.count()
            current_active = Senador.objects.filter(is_active=True).count()
            current_inactive = Senador.objects.filter(is_active=False).count()
            
            self.stdout.write(f"📊 Current database state:")
            self.stdout.write(f"   Total senators: {total_senators}")
            self.stdout.write(f"   Active: {current_active}")
            self.stdout.write(f"   Inactive: {current_inactive}")
            
            # Calculate what will change
            existing_senators = Senador.objects.values_list('api_id', 'is_active')
            # Ensure consistent string format for comparison
            existing_dict = {str(api_id): is_active for api_id, is_active in existing_senators}
            
            will_activate = []
            will_deactivate = []
            
            for api_id, current_status in existing_dict.items():
                should_be_active = api_id in current_api_ids
                
                if should_be_active and not current_status:
                    will_activate.append(api_id)
                elif not should_be_active and current_status:
                    will_deactivate.append(api_id)
            
            self.stdout.write(f"\n📋 Changes to be made:")
            self.stdout.write(f"   Senators to activate: {len(will_activate)}")
            self.stdout.write(f"   Senators to deactivate: {len(will_deactivate)}")
            
            if options['dry_run']:
                self.stdout.write("\n🔍 DRY RUN - No changes will be made")
                
                if will_activate:
                    self.stdout.write(f"\nWould ACTIVATE {len(will_activate)} senators:")
                    for api_id in will_activate[:10]:  # Show first 10
                        senator = Senador.objects.get(api_id=api_id)
                        self.stdout.write(f"   ✅ {senator.nome_parlamentar} (ID: {api_id})")
                    if len(will_activate) > 10:
                        self.stdout.write(f"   ... and {len(will_activate) - 10} more")
                
                if will_deactivate:
                    self.stdout.write(f"\nWould DEACTIVATE {len(will_deactivate)} senators:")
                    for api_id in will_deactivate[:10]:  # Show first 10
                        senator = Senador.objects.get(api_id=api_id)
                        self.stdout.write(f"   ❌ {senator.nome_parlamentar} (ID: {api_id})")
                    if len(will_deactivate) > 10:
                        self.stdout.write(f"   ... and {len(will_deactivate) - 10} more")
                
                self.stdout.write(f"\nFinal result would be: {len(current_api_ids)} active senators")
                return
            
            # Perform the sync
            with transaction.atomic():
                self.stdout.write("\n🔄 Updating senator status...")
                
                # Mark all as inactive first
                Senador.objects.all().update(is_active=False)
                
                # Mark current API senators as active
                # Convert back to the original format for database filtering
                api_ids_for_db = list(current_api_ids)
                activated_count = Senador.objects.filter(api_id__in=api_ids_for_db).update(is_active=True)
                
            # Verify final state
            final_active = Senador.objects.filter(is_active=True).count()
            final_inactive = Senador.objects.filter(is_active=False).count()
            
            self.stdout.write(f"\n✅ Synchronization completed successfully!")
            self.stdout.write(f"📊 Final database state:")
            self.stdout.write(f"   Total senators: {total_senators}")
            self.stdout.write(f"   Active: {final_active}")
            self.stdout.write(f"   Inactive: {final_inactive}")
            
            if final_active == len(current_api_ids):
                self.stdout.write(f"🎉 Perfect match! Database now has {final_active} active senators matching the official API")
            else:
                self.stdout.write(f"⚠️  Warning: Database has {final_active} active senators but API has {len(current_api_ids)}")
                
        except requests.RequestException as e:
            self.stdout.write(f"❌ Error fetching data from official API: {str(e)}")
            return
        except ET.ParseError as e:
            self.stdout.write(f"❌ Error parsing XML response: {str(e)}")
            return
        except Exception as e:
            self.stdout.write(f"❌ Error during synchronization: {str(e)}")
            return
    
    def _get_xml_text(self, parent, tag_name: str):
        """
        Safely extract text content from XML element
        
        Args:
            parent: Parent XML element
            tag_name: Name of the child tag to extract
            
        Returns:
            Text content or None if not found
        """
        if parent is None:
            return None
            
        element = parent.find(tag_name)
        if element is not None and element.text:
            return element.text.strip()
        return None