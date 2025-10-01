"""
Django management command to collect tweets from politicians using browser automation
"""

import time
from datetime import datetime
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from pressionaapp.models import Deputado, Senador


class TwitterProfileTweetCollector:
    def __init__(self, stdout):
        self.driver = None
        self.collected_tweets = []
        self.stdout = stdout
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        self.stdout.write("🌐 Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # Automatically download and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.stdout.write("✅ Chrome WebDriver initialized successfully")
        except Exception as e:
            self.stdout.write(f"❌ Error setting up WebDriver: {str(e)}")
            self.stdout.write("💡 Make sure you have Chrome browser installed")
            raise
    
    def open_twitter_and_login(self):
        """Open Twitter/X and wait for user to login manually"""
        self.stdout.write("\n🔐 Opening Twitter/X for manual login...")
        
        try:
            # Go to Twitter login page
            self.driver.get("https://x.com/login")
            self.stdout.write("📱 Twitter/X login page opened")
            
            # Wait for user to login manually
            self.stdout.write("\n" + "="*60)
            self.stdout.write("🚨 MANUAL LOGIN REQUIRED")
            self.stdout.write("="*60)
            self.stdout.write("1. Please login to your Twitter/X account in the browser")
            self.stdout.write("2. Complete any 2FA or verification steps")
            self.stdout.write("3. Wait until you see your Twitter/X home feed")
            self.stdout.write("4. Then press ENTER in this console to continue...")
            self.stdout.write("="*60)
            
            input("\n⏳ Press ENTER after you've successfully logged in: ")
            
            # Verify login by checking for home page elements
            self.stdout.write("\n🔍 Verifying login status...")
            time.sleep(3)
            
            current_url = self.driver.current_url
            if "home" in current_url or "x.com" in current_url:
                self.stdout.write("✅ Login verification successful!")
                return True
            else:
                self.stdout.write(f"⚠️  Current URL: {current_url}")
                self.stdout.write("❌ Login might not be complete. Continuing anyway...")
                return False
                
        except Exception as e:
            self.stdout.write(f"❌ Error during login process: {str(e)}")
            return False
    
    def get_politicians_from_database(self, limit=None, politicians_type='both'):
        """Get politicians with Twitter URLs from database"""
        self.stdout.write("🗄️  Loading politicians from database...")
        
        politicians = []
        deputies_count = 0
        senators_count = 0
        
        # Get deputies if requested
        if politicians_type in ['both', 'deputies']:
            deputies_query = Deputado.objects.filter(
                twitter_url__isnull=False,
                is_active=True
            ).exclude(twitter_url='').order_by('nome_parlamentar')
            
            if limit and politicians_type == 'deputies':
                # If only deputies and limit specified, apply limit to deputies
                deputies_query = deputies_query[:limit]
            elif limit and politicians_type == 'both':
                # If both types and limit specified, apply half limit to deputies
                deputies_query = deputies_query[:limit//2]
            
            for deputy in deputies_query:
                politicians.append({
                    'type': 'Deputado',
                    'name': deputy.nome_parlamentar,
                    'party': deputy.partido,
                    'state': deputy.uf,
                    'twitter_url': deputy.twitter_url,
                    'username': self.extract_username_from_url(deputy.twitter_url),
                    'id': deputy.id
                })
                deputies_count += 1
        
        # Get senators if requested
        if politicians_type in ['both', 'senators']:
            senators_query = Senador.objects.filter(
                twitter_url__isnull=False,
                is_active=True
            ).exclude(twitter_url='').order_by('nome_parlamentar')
            
            if limit and politicians_type == 'senators':
                # If only senators and limit specified, apply limit to senators
                senators_query = senators_query[:limit]
            elif limit and politicians_type == 'both':
                # If both types and limit specified, apply remaining limit to senators
                remaining_limit = limit - deputies_count
                senators_query = senators_query[:remaining_limit]
            
            for senator in senators_query:
                politicians.append({
                    'type': 'Senador',
                    'name': senator.nome_parlamentar,
                    'party': senator.partido,
                    'state': senator.uf,
                    'twitter_url': senator.twitter_url,
                    'username': self.extract_username_from_url(senator.twitter_url),
                    'id': senator.id
                })
                senators_count += 1
        
        # Apply final limit if both types and total exceeds limit
        if limit and politicians_type == 'both' and len(politicians) > limit:
            politicians = politicians[:limit]
            self.stdout.write(f"🔢 Applied final limit of {limit} politicians")
        
        self.stdout.write(f"📊 Found {len(politicians)} politicians with Twitter profiles:")
        if deputies_count > 0:
            self.stdout.write(f"   📋 Deputies: {deputies_count}")
        if senators_count > 0:
            self.stdout.write(f"   🏛️  Senators: {senators_count}")
        
        if limit:
            self.stdout.write(f"   🔢 Limited to: {limit} total")
        
        return politicians
    
    def extract_username_from_url(self, twitter_url):
        """Extract username from Twitter URL"""
        if not twitter_url:
            return None
        
        # Remove protocol and domain
        username = twitter_url.replace('https://', '').replace('http://', '')
        username = username.replace('x.com/', '').replace('twitter.com/', '')
        
        # Remove any path after username
        if '/' in username:
            username = username.split('/')[0]
        
        # Remove query parameters
        if '?' in username:
            username = username.split('?')[0]
        
        return username.strip()
    
    def visit_profile_and_get_latest_tweet(self, politician):
        """Visit politician's profile and get their latest tweet"""
        username = politician['username']
        name = politician['name']
        
        self.stdout.write(f"\n[🔍] Checking @{username} ({name})")
        self.stdout.write("-" * 50)
        
        try:
            # Navigate to the profile
            profile_url = f"https://x.com/{username}"
            self.stdout.write(f"📱 Visiting: {profile_url}")
            self.driver.get(profile_url)
            
            # Wait for page to load
            time.sleep(4)
            
            # Check if profile is accessible
            page_source = self.driver.page_source.lower()
            
            # Check for suspension or not found
            if any(indicator in page_source for indicator in [
                "account suspended", "this account has been suspended",
                "this account doesn't exist", "sorry, that page doesn't exist"
            ]):
                self.stdout.write("❌ Profile suspended or not found")
                return self.create_result_entry(politician, "suspended", None)
            
            self.stdout.write("✅ Profile accessible")
            
            # Try to find the latest tweet
            try:
                # Wait for tweets to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweet"]'))
                )
                
                # Find the first tweet (most recent)
                tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
                
                if not tweet_elements:
                    self.stdout.write("❌ No tweets found")
                    return self.create_result_entry(politician, "no_tweets", None)
                
                # Get the first tweet (most recent)
                first_tweet = tweet_elements[0]
                
                # Extract tweet data
                tweet_data = self.extract_tweet_data(first_tweet, username)
                
                if tweet_data:
                    self.stdout.write(f"✅ Latest tweet found!")
                    self.stdout.write(f"   📅 Date: {tweet_data.get('date', 'Unknown')}")
                    self.stdout.write(f"   🔗 URL: {tweet_data.get('url', 'N/A')}")
                    self.stdout.write(f"   💬 Text: {tweet_data.get('text', '')[:100]}...")
                    
                    return self.create_result_entry(politician, "success", tweet_data)
                else:
                    self.stdout.write("⚠️  Could not extract tweet data")
                    return self.create_result_entry(politician, "extraction_failed", None)
                
            except TimeoutException:
                self.stdout.write("❌ Timeout waiting for tweets to load")
                return self.create_result_entry(politician, "timeout", None)
            
        except Exception as e:
            self.stdout.write(f"❌ Error visiting profile: {str(e)}")
            return self.create_result_entry(politician, "error", None, str(e))
    
    def extract_tweet_data(self, tweet_element, username):
        """Extract data from a tweet element"""
        try:
            tweet_data = {
                'username': username,
                'text': '',
                'date': '',
                'url': '',
                'likes': 0,
                'retweets': 0,
                'replies': 0
            }
            
            # Extract tweet text
            try:
                text_elements = tweet_element.find_elements(By.CSS_SELECTOR, '[data-testid="tweetText"]')
                if text_elements:
                    tweet_data['text'] = text_elements[0].text
            except:
                pass
            
            # Extract tweet date/time
            try:
                time_elements = tweet_element.find_elements(By.TAG_NAME, "time")
                if time_elements:
                    tweet_data['date'] = time_elements[0].get_attribute("datetime")
            except:
                pass
            
            # Extract tweet URL
            try:
                link_elements = tweet_element.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
                if link_elements:
                    href = link_elements[0].get_attribute('href')
                    if href:
                        tweet_data['url'] = href
            except:
                pass
            
            # Extract engagement metrics (likes, retweets, replies)
            try:
                # Try to find metric buttons
                metric_buttons = tweet_element.find_elements(By.CSS_SELECTOR, '[role="button"]')
                for button in metric_buttons:
                    aria_label = button.get_attribute('aria-label') or ''
                    
                    if 'like' in aria_label.lower():
                        # Extract number from aria-label
                        import re
                        numbers = re.findall(r'\\d+', aria_label.replace(',', ''))
                        if numbers:
                            tweet_data['likes'] = int(numbers[0])
                    
                    elif 'repost' in aria_label.lower() or 'retweet' in aria_label.lower():
                        numbers = re.findall(r'\\d+', aria_label.replace(',', ''))
                        if numbers:
                            tweet_data['retweets'] = int(numbers[0])
                    
                    elif 'repl' in aria_label.lower():
                        numbers = re.findall(r'\\d+', aria_label.replace(',', ''))
                        if numbers:
                            tweet_data['replies'] = int(numbers[0])
            except:
                pass
            
            return tweet_data
            
        except Exception as e:
            self.stdout.write(f"⚠️  Error extracting tweet data: {str(e)}")
            return None
    
    def create_result_entry(self, politician, status, tweet_data, error=None):
        """Create a standardized result entry"""
        return {
            'politician_type': politician['type'],
            'politician_name': politician['name'],
            'politician_party': politician['party'],
            'politician_state': politician['state'],
            'twitter_username': politician['username'],
            'twitter_url': politician['twitter_url'],
            'status': status,
            'tweet_text': tweet_data.get('text', '') if tweet_data else '',
            'tweet_date': tweet_data.get('date', '') if tweet_data else '',
            'tweet_url': tweet_data.get('url', '') if tweet_data else '',
            'tweet_likes': tweet_data.get('likes', 0) if tweet_data else 0,
            'tweet_retweets': tweet_data.get('retweets', 0) if tweet_data else 0,
            'tweet_replies': tweet_data.get('replies', 0) if tweet_data else 0,
            'extraction_time': datetime.now().isoformat(),
            'error_message': error or ''
        }
    
    def run_collection(self, limit=None, politicians_type='both'):
        """Run the complete tweet collection process"""
        self.stdout.write("=" * 80)
        self.stdout.write("🏛️  TWITTER TWEET COLLECTION FOR BRAZILIAN POLITICIANS")
        self.stdout.write("=" * 80)
        
        # Step 1: Open Twitter and wait for login
        if not self.open_twitter_and_login():
            self.stdout.write("❌ Login process failed. Exiting...")
            return
        
        # Step 2: Get politicians from database
        politicians = self.get_politicians_from_database(limit, politicians_type)
        
        if not politicians:
            self.stdout.write("❌ No politicians with Twitter profiles found in database")
            return
        
        # Step 3: Process each politician
        self.stdout.write(f"\n🔍 Starting tweet collection for {len(politicians)} politicians...")
        start_time = datetime.now()
        
        successful_collections = 0
        failed_collections = 0
        
        for i, politician in enumerate(politicians, 1):
            self.stdout.write(f"\n[{i:3d}/{len(politicians)}] Processing {politician['name']} (@{politician['username']})")
            
            result = self.visit_profile_and_get_latest_tweet(politician)
            self.collected_tweets.append(result)
            
            if result['status'] == 'success':
                successful_collections += 1
            else:
                failed_collections += 1
            
            # Small delay between requests to be respectful
            time.sleep(2)
            
            # Longer pause every 20 profiles
            if i % 20 == 0:
                self.stdout.write(f"\n⏸️  Pausing for 10 seconds (processed {i}/{len(politicians)})...")
                time.sleep(10)
        
        # Step 4: Show final results and save
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📊 COLLECTION RESULTS SUMMARY")
        self.stdout.write("=" * 80)
        
        self.stdout.write(f"⏱️  Total time: {duration/60:.1f} minutes")
        self.stdout.write(f"👥 Politicians processed: {len(politicians)}")
        self.stdout.write(f"✅ Successful collections: {successful_collections}")
        self.stdout.write(f"❌ Failed collections: {failed_collections}")
        self.stdout.write(f"📈 Success rate: {successful_collections/len(politicians)*100:.1f}%")
        
        # Show breakdown by status
        status_counts = {}
        for result in self.collected_tweets:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        self.stdout.write(f"\n📋 Status breakdown:")
        for status, count in status_counts.items():
            self.stdout.write(f"   {status}: {count}")
        
        self.stdout.write("=" * 80)
        
        return self.collected_tweets
    
    def cleanup(self):
        """Close the browser"""
        if self.driver:
            self.stdout.write("\n🔄 Closing browser...")
            self.driver.quit()
            self.stdout.write("✅ Browser closed")


class Command(BaseCommand):
    help = 'Collect latest tweets from politicians using browser automation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of politicians to process (default: all)',
        )
        parser.add_argument(
            '--type',
            choices=['deputies', 'senators', 'both'],
            default='both',
            help='Type of politicians to collect tweets from (default: both)',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        politicians_type = options.get('type')
        
        self.stdout.write("🚀 Starting Twitter Tweet Collection for Politicians...")
        self.stdout.write("💡 Make sure you have Chrome browser installed")
        self.stdout.write("💡 You'll need to manually login to Twitter/X when prompted")
        self.stdout.write("💡 This process may take a while depending on the number of politicians")
        
        if limit:
            self.stdout.write(f"🔢 Limit: {limit} politicians")
        
        type_display = {
            'deputies': 'Deputados apenas',
            'senators': 'Senadores apenas', 
            'both': 'Deputados e Senadores'
        }
        self.stdout.write(f"👥 Tipo: {type_display[politicians_type]}")
        
        input("\n⏳ Press ENTER to start the browser...")
        
        collector = None
        
        try:
            collector = TwitterProfileTweetCollector(self.stdout)
            results = collector.run_collection(limit, politicians_type)
            
            self.stdout.write(f"\n🎉 Tweet collection complete!")
            self.stdout.write(f"📊 Total results: {len(results)}")
            
        except KeyboardInterrupt:
            self.stdout.write("\n⏹️  Process interrupted by user")
        except Exception as e:
            self.stdout.write(f"\n❌ Unexpected error: {str(e)}")
        finally:
            if collector:
                collector.cleanup()