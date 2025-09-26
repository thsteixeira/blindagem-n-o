"""
Simple command to extract and save congress data using simplified models
"""

from django.core.management.base import BaseCommand
from pressionaapp.deputados_extractor import DeputadosDataExtractor
from pressionaapp.senadores_extractor import SenadoresDataExtractor


class Command(BaseCommand):
    help = 'Extract and save congress data (deputies and senators) with simplified models'

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
            '--skip-social-media',
            action='store_true',
            help='Skip social media extraction for deputies (faster)',
        )
        parser.add_argument(
            '--no-update',
            action='store_true',
            help='Do not update existing records',
        )
        parser.add_argument(
            '--no-google-fallback',
            action='store_true',
            help='Disable Google search fallback for deputies with no social media found on Chamber website (faster but less complete)',
        )
        parser.add_argument(
            '--twitter-only',
            action='store_true',
            help='Search only for Twitter/X links (much faster, skips Instagram and Facebook)',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting congress data extraction...")
        
        extract_social_media = not options['skip_social_media']
        update_existing = not options['no_update']
        use_google_fallback = not options['no_google_fallback']  # Default True, disable with --no-google-fallback
        twitter_only = options['twitter_only']
        
        if not options['senators_only']:
            self.stdout.write("\n📋 EXTRACTING DEPUTIES...")
            self.stdout.write(f"   Social media extraction: {'ON' if extract_social_media else 'OFF'}")
            self.stdout.write(f"   Google search fallback: {'ON' if use_google_fallback else 'OFF'}")
            self.stdout.write(f"   Twitter only mode: {'ON' if twitter_only else 'OFF'}")
            self.stdout.write(f"   Update existing: {'ON' if update_existing else 'OFF'}")
            
            try:
                extractor = DeputadosDataExtractor()
                created, updated = extractor.extract_deputies(
                    update_existing=update_existing,
                    extract_social_media=extract_social_media,
                    use_google_fallback=use_google_fallback,
                    twitter_only=twitter_only,
                    limit=options.get('limit')
                )
                self.stdout.write(f"✅ Deputies: {created} created, {updated} updated")
            except Exception as e:
                self.stdout.write(f"❌ Error extracting deputies: {str(e)}")
        
        if not options['deputies_only']:
            self.stdout.write("\n🏛️  EXTRACTING SENATORS...")
            self.stdout.write(f"   Social media extraction: {'ON' if extract_social_media else 'OFF'}")
            self.stdout.write(f"   Google search fallback: {'ON' if use_google_fallback else 'OFF'}")
            self.stdout.write(f"   Twitter only mode: {'ON' if twitter_only else 'OFF'}")
            self.stdout.write(f"   Update existing: {'ON' if update_existing else 'OFF'}")
            
            try:
                extractor = SenadoresDataExtractor()
                created, updated = extractor.extract_all_senators(
                    limit=options.get('limit'),
                    extract_social_media=extract_social_media,
                    use_google_fallback=use_google_fallback,
                    twitter_only=twitter_only
                )
                self.stdout.write(f"✅ Senators: {created} created, {updated} updated")
            except Exception as e:
                self.stdout.write(f"❌ Error extracting senators: {str(e)}")
        
        self.stdout.write("\n🎉 Congress data extraction completed!")