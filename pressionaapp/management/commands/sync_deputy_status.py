"""
Django management command to synchronize deputy active status with official Chamber API
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import requests
from pressionaapp.models import Deputado


class Command(BaseCommand):
    help = 'Synchronize deputy active status with official Chamber of Deputies API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making any modifications',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Starting deputy status synchronization with official API...")
        
        try:
            # Fetch current deputies from official API
            self.stdout.write("📡 Fetching current deputies from official Chamber API...")
            response = requests.get('https://dadosabertos.camara.leg.br/api/v2/deputados')
            response.raise_for_status()
            
            api_data = response.json()
            current_api_ids = {str(dep['id']) for dep in api_data['dados']}
            
            self.stdout.write(f"✅ Found {len(current_api_ids)} active deputies in official API")
            
            # Get current database state
            total_deputies = Deputado.objects.count()
            current_active = Deputado.objects.filter(is_active=True).count()
            current_inactive = Deputado.objects.filter(is_active=False).count()
            
            self.stdout.write(f"📊 Current database state:")
            self.stdout.write(f"   Total deputies: {total_deputies}")
            self.stdout.write(f"   Active: {current_active}")
            self.stdout.write(f"   Inactive: {current_inactive}")
            
            # Calculate what will change
            existing_deputies = Deputado.objects.values_list('api_id', 'is_active')
            existing_dict = {api_id: is_active for api_id, is_active in existing_deputies}
            
            will_activate = []
            will_deactivate = []
            
            for api_id, current_status in existing_dict.items():
                should_be_active = api_id in current_api_ids
                
                if should_be_active and not current_status:
                    will_activate.append(api_id)
                elif not should_be_active and current_status:
                    will_deactivate.append(api_id)
            
            self.stdout.write(f"\n📋 Changes to be made:")
            self.stdout.write(f"   Deputies to activate: {len(will_activate)}")
            self.stdout.write(f"   Deputies to deactivate: {len(will_deactivate)}")
            
            if options['dry_run']:
                self.stdout.write("\n🔍 DRY RUN - No changes will be made")
                
                if will_activate:
                    self.stdout.write(f"\nWould ACTIVATE {len(will_activate)} deputies:")
                    for api_id in will_activate[:10]:  # Show first 10
                        deputy = Deputado.objects.get(api_id=api_id)
                        self.stdout.write(f"   ✅ {deputy.nome_parlamentar} (ID: {api_id})")
                    if len(will_activate) > 10:
                        self.stdout.write(f"   ... and {len(will_activate) - 10} more")
                
                if will_deactivate:
                    self.stdout.write(f"\nWould DEACTIVATE {len(will_deactivate)} deputies:")
                    for api_id in will_deactivate[:10]:  # Show first 10
                        deputy = Deputado.objects.get(api_id=api_id)
                        self.stdout.write(f"   ❌ {deputy.nome_parlamentar} (ID: {api_id})")
                    if len(will_deactivate) > 10:
                        self.stdout.write(f"   ... and {len(will_deactivate) - 10} more")
                
                self.stdout.write(f"\nFinal result would be: {len(current_api_ids)} active deputies")
                return
            
            # Perform the sync
            with transaction.atomic():
                self.stdout.write("\n🔄 Updating deputy status...")
                
                # Mark all as inactive first
                Deputado.objects.all().update(is_active=False)
                
                # Mark current API deputies as active
                activated_count = Deputado.objects.filter(api_id__in=current_api_ids).update(is_active=True)
                
            # Verify final state
            final_active = Deputado.objects.filter(is_active=True).count()
            final_inactive = Deputado.objects.filter(is_active=False).count()
            
            self.stdout.write(f"\n✅ Synchronization completed successfully!")
            self.stdout.write(f"📊 Final database state:")
            self.stdout.write(f"   Total deputies: {total_deputies}")
            self.stdout.write(f"   Active: {final_active}")
            self.stdout.write(f"   Inactive: {final_inactive}")
            
            if final_active == len(current_api_ids):
                self.stdout.write(f"🎉 Perfect match! Database now has {final_active} active deputies matching the official API")
            else:
                self.stdout.write(f"⚠️  Warning: Database has {final_active} active deputies but API has {len(current_api_ids)}")
                
        except requests.RequestException as e:
            self.stdout.write(f"❌ Error fetching data from official API: {str(e)}")
            return
        except Exception as e:
            self.stdout.write(f"❌ Error during synchronization: {str(e)}")
            return