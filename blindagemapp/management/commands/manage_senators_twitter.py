from django.core.management.base import BaseCommand
from blindagemapp.models import Senador
import json
import re


class Command(BaseCommand):
    help = 'Manually add Twitter accounts for senators and export to JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--add',
            nargs=2,
            metavar=('SENATOR_NAME', 'TWITTER_URL'),
            help='Add Twitter URL for a specific senator: --add "Senator Name" "https://twitter.com/handle"',
        )
        parser.add_argument(
            '--export-json',
            action='store_true',
            help='Export all senators with Twitter accounts to JSON',
        )
        parser.add_argument(
            '--list-without-twitter',
            action='store_true',
            help='List senators without Twitter accounts',
        )
        parser.add_argument(
            '--search-template',
            action='store_true',
            help='Generate search URLs for manual searching',
        )

    def handle(self, *args, **options):
        if options['add']:
            self.add_twitter_account(options['add'][0], options['add'][1])
        
        if options['list_without_twitter']:
            self.list_senators_without_twitter()
            
        if options['search_template']:
            self.generate_search_templates()
            
        if options['export_json']:
            self.export_to_json()

    def add_twitter_account(self, senator_name, twitter_url):
        """Add Twitter account for a senator"""
        try:
            # Find senator by name (fuzzy match)
            senators = Senador.objects.filter(nome_parlamentar__icontains=senator_name)
            
            if not senators.exists():
                self.stdout.write(f"❌ Senator not found: {senator_name}")
                self.suggest_similar_names(senator_name)
                return
            
            if senators.count() > 1:
                self.stdout.write(f"⚠️  Multiple senators found for '{senator_name}':")
                for senator in senators:
                    self.stdout.write(f"   - {senator.nome_parlamentar}")
                self.stdout.write("Please be more specific.")
                return
            
            senator = senators.first()
            
            # Validate Twitter URL
            if not self.is_valid_twitter_url(twitter_url):
                self.stdout.write(f"❌ Invalid Twitter URL: {twitter_url}")
                return
            
            # Normalize URL
            normalized_url = self.normalize_twitter_url(twitter_url)
            
            # Update senator
            senator.twitter_url = normalized_url
            senator.save()
            
            self.stdout.write(f"✅ Updated {senator.nome_parlamentar}: {normalized_url}")
            
        except Exception as e:
            self.stdout.write(f"❌ Error: {str(e)}")

    def list_senators_without_twitter(self):
        """List all senators without Twitter accounts"""
        senators = Senador.objects.filter(twitter_url__isnull=True).order_by('nome_parlamentar')
        
        self.stdout.write(f"\n📋 SENATORS WITHOUT TWITTER ACCOUNTS ({senators.count()}):")
        self.stdout.write("=" * 60)
        
        for i, senator in enumerate(senators, 1):
            self.stdout.write(f"{i:3d}. {senator.nome_parlamentar} ({senator.partido}/{senator.uf})")
            
        self.stdout.write(f"\nTotal: {senators.count()} senators need Twitter accounts")

    def generate_search_templates(self):
        """Generate search URLs for manual searching"""
        senators = Senador.objects.filter(twitter_url__isnull=True).order_by('nome_parlamentar')[:10]
        
        self.stdout.write("\n🔍 MANUAL SEARCH TEMPLATES (first 10):")
        self.stdout.write("=" * 60)
        
        for senator in senators:
            search_name = senator.nome_parlamentar.replace(' ', '+')
            google_url = f"https://www.google.com/search?q=senador+{search_name}+twitter"
            self.stdout.write(f"\n{senator.nome_parlamentar}:")
            self.stdout.write(f"  Google: {google_url}")
            self.stdout.write(f"  Command: python manage.py manage_senators_twitter --add \"{senator.nome_parlamentar}\" \"TWITTER_URL_HERE\"")

    def export_to_json(self):
        """Export senators with Twitter accounts to JSON"""
        senators_with_twitter = Senador.objects.filter(twitter_url__isnull=False).exclude(twitter_url='')
        
        export_data = []
        for senator in senators_with_twitter:
            # Extract handle from URL
            handle = self.extract_handle_from_url(senator.twitter_url)
            
            export_data.append({
                'id': senator.id,
                'api_id': senator.api_id,  # Use the simplified api_id field
                'name': senator.nome_parlamentar,
                'x_account': f"@{handle}" if handle else senator.twitter_url
            })
        
        filename = 'senators_x_accounts.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        self.stdout.write(f"📄 Exported {len(export_data)} senators to {filename}")

    def suggest_similar_names(self, search_name):
        """Suggest similar senator names"""
        all_senators = Senador.objects.all()
        suggestions = []
        
        search_lower = search_name.lower()
        for senator in all_senators:
            name_lower = senator.nome_parlamentar.lower()
            # Simple similarity check
            if any(word in name_lower for word in search_lower.split()):
                suggestions.append(senator.nome_parlamentar)
        
        if suggestions:
            self.stdout.write("💡 Did you mean:")
            for suggestion in suggestions[:5]:  # Show top 5
                self.stdout.write(f"   - {suggestion}")

    def is_valid_twitter_url(self, url):
        """Validate Twitter URL format"""
        patterns = [
            r'https?://(www\.)?(twitter\.com|x\.com)/[a-zA-Z0-9_]+/?$',
            r'@[a-zA-Z0-9_]+$',  # Just handle
        ]
        
        return any(re.match(pattern, url, re.IGNORECASE) for pattern in patterns)

    def normalize_twitter_url(self, url):
        """Normalize Twitter URL to standard format"""
        # If it's just a handle
        if url.startswith('@'):
            return f"https://twitter.com/{url[1:]}"
        
        # If it's an x.com URL, convert to twitter.com
        if 'x.com/' in url:
            handle = url.split('x.com/')[-1].split('/')[0]
            return f"https://twitter.com/{handle}"
        
        # If it's already a twitter.com URL, ensure proper format
        if 'twitter.com/' in url:
            handle = url.split('twitter.com/')[-1].split('/')[0]
            return f"https://twitter.com/{handle}"
        
        return url

    def extract_handle_from_url(self, url):
        """Extract username from Twitter URL"""
        if not url:
            return None
            
        match = re.search(r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)', url)
        return match.group(1) if match else None