"""
Simple command to extract and save congress data using simplified models
"""

from django.core.management.base import BaseCommand
from pressionaapp.deputados_extractor import DeputadosDataExtractor
from pressionaapp.senadores_extractor import SenadoresDataExtractor


class Command(BaseCommand):
    help = 'Extract and save congress data (deputies and senators) using Grok API integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--deputies-only',
            action='store_true',
            help='Extract only deputies data',
        )
        parser.add_argument(
            '--senators-only',
            action='store_true',
            help='Extract only senators data',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to process (for testing)',
        )
        parser.add_argument(
            '--no-update',
            action='store_true',
            help='Do not update existing records',
        )


    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting congress data extraction with Grok API...")
        
        update_existing = not options['no_update']
        limit = options.get('limit')
        
        if not options['senators_only']:
            self.stdout.write("\n📋 EXTRACTING DEPUTIES...")
            self.stdout.write(f"   Grok API integration: ON")
            self.stdout.write(f"   Update existing: {'ON' if update_existing else 'OFF'}")
            if limit:
                self.stdout.write(f"   Limit: {limit} records")
            
            try:
                extractor = DeputadosDataExtractor()
                created, updated = extractor.extract_deputies(
                    update_existing=update_existing,
                    limit=options.get('limit')
                )
                self.stdout.write(f"✅ Deputies: {created} created, {updated} updated")
            except Exception as e:
                self.stdout.write(f"❌ Error extracting deputies: {str(e)}")
        
        if not options['deputies_only']:
            self.stdout.write("\n🏛️  EXTRACTING SENATORS...")
            self.stdout.write(f"   Grok API integration: ON")
            self.stdout.write(f"   Update existing: {'ON' if update_existing else 'OFF'}")
            if limit:
                self.stdout.write(f"   Limit: {limit} records")
            
            try:
                extractor = SenadoresDataExtractor()
                created, updated = extractor.extract_senators(
                    limit=options.get('limit'),
                    update_existing=update_existing
                )
                self.stdout.write(f"✅ Senators: {created} created, {updated} updated")
            except Exception as e:
                self.stdout.write(f"❌ Error extracting senators: {str(e)}")
        
        self.stdout.write("\n🎉 Congress data extraction completed!")