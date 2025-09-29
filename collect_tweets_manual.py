#!/usr/bin/env python
"""
Browser automation script to manually collect latest tweets from all politicians in database
Opens Twitter/X, waits for manual login, then searches for latest tweets from all saved profiles
"""

import os
import sys
import django
import time
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pressiona.settings')
django.setup()

from pressionaapp.models import Deputado, Senador

class TwitterProfileTweetCollector:
    def __init__(self):
        self.driver = None
        self.collected_tweets = []
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        print("🌐 Setting up Chrome WebDriver...")
        
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
            print("✅ Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"❌ Error setting up WebDriver: {str(e)}")
            print("💡 Make sure you have Chrome browser installed")
            raise
    
    def open_twitter_and_login(self):
        """Open Twitter/X and wait for user to login manually"""
        print("\n🔐 Opening Twitter/X for manual login...")
        
        try:
            # Go to Twitter login page
            self.driver.get("https://x.com/login")
            print("📱 Twitter/X login page opened")
            
            # Wait for user to login manually
            print("\n" + "="*60)
            print("🚨 MANUAL LOGIN REQUIRED")
            print("="*60)
            print("1. Please login to your Twitter/X account in the browser")
            print("2. Complete any 2FA or verification steps")
            print("3. Wait until you see your Twitter/X home feed")
            print("4. Then press ENTER in this console to continue...")
            print("="*60)
            
            input("\n⏳ Press ENTER after you've successfully logged in: ")
            
            # Verify login by checking for home page elements
            print("\n🔍 Verifying login status...")
            time.sleep(3)
            
            current_url = self.driver.current_url
            if "home" in current_url or "x.com" in current_url:
                print("✅ Login verification successful!")
                return True
            else:
                print(f"⚠️  Current URL: {current_url}")
                print("❌ Login might not be complete. Continuing anyway...")
                return False
                
        except Exception as e:
            print(f"❌ Error during login process: {str(e)}")
            return False
    
    def get_politicians_from_database(self):
        """Get all politicians with Twitter URLs from database"""
        print("🗄️  Loading politicians from database...")
        
        politicians = []
        
        # Get deputies with Twitter URLs
        deputies = Deputado.objects.filter(
            twitter_url__isnull=False,
            is_active=True
        ).exclude(twitter_url='')
        
        for deputy in deputies:
            politicians.append({
                'type': 'Deputado',
                'name': deputy.nome_parlamentar,
                'party': deputy.partido,
                'state': deputy.uf,
                'twitter_url': deputy.twitter_url,
                'username': self.extract_username_from_url(deputy.twitter_url),
                'id': deputy.id
            })
        
        # Get senators with Twitter URLs
        senators = Senador.objects.filter(
            twitter_url__isnull=False,
            is_active=True
        ).exclude(twitter_url='')
        
        for senator in senators:
            politicians.append({
                'type': 'Senador',
                'name': senator.nome_parlamentar,
                'party': senator.partido,
                'state': senator.uf,
                'twitter_url': senator.twitter_url,
                'username': self.extract_username_from_url(senator.twitter_url),
                'id': senator.id
            })
        
        print(f"📊 Found {len(politicians)} politicians with Twitter profiles:")
        print(f"   📋 Deputies: {len(deputies)}")
        print(f"   🏛️  Senators: {len(senators)}")
        
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
        
        print(f"\n[🔍] Checking @{username} ({name})")
        print("-" * 50)
        
        try:
            # Navigate to the profile
            profile_url = f"https://x.com/{username}"
            print(f"📱 Visiting: {profile_url}")
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
                print("❌ Profile suspended or not found")
                return self.create_result_entry(politician, "suspended", None)
            
            print("✅ Profile accessible")
            
            # Try to find the latest tweet
            try:
                # Wait for tweets to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweet"]'))
                )
                
                # Find the first tweet (most recent)
                tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
                
                if not tweet_elements:
                    print("❌ No tweets found")
                    return self.create_result_entry(politician, "no_tweets", None)
                
                # Get the first tweet (most recent)
                first_tweet = tweet_elements[0]
                
                # Extract tweet data
                tweet_data = self.extract_tweet_data(first_tweet, username)
                
                if tweet_data:
                    print(f"✅ Latest tweet found!")
                    print(f"   📅 Date: {tweet_data.get('date', 'Unknown')}")
                    print(f"   🔗 URL: {tweet_data.get('url', 'N/A')}")
                    print(f"   💬 Text: {tweet_data.get('text', '')[:100]}...")
                    
                    return self.create_result_entry(politician, "success", tweet_data)
                else:
                    print("⚠️  Could not extract tweet data")
                    return self.create_result_entry(politician, "extraction_failed", None)
                
            except TimeoutException:
                print("❌ Timeout waiting for tweets to load")
                return self.create_result_entry(politician, "timeout", None)
            
        except Exception as e:
            print(f"❌ Error visiting profile: {str(e)}")
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
            print(f"⚠️  Error extracting tweet data: {str(e)}")
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
    
    def save_results_to_csv(self, filename=None):
        """Save collected results to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"politicians_tweets_collection_{timestamp}.csv"
        
        print(f"\n💾 Saving results to: {filename}")
        
        if not self.collected_tweets:
            print("⚠️  No data to save")
            return
        
        fieldnames = [
            'politician_type', 'politician_name', 'politician_party', 'politician_state',
            'twitter_username', 'twitter_url', 'status',
            'tweet_text', 'tweet_date', 'tweet_url',
            'tweet_likes', 'tweet_retweets', 'tweet_replies',
            'extraction_time', 'error_message'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.collected_tweets)
        
        print(f"✅ Results saved to {filename}")
    
    def run_collection(self):
        """Run the complete tweet collection process"""
        print("=" * 80)
        print("🏛️  TWITTER TWEET COLLECTION FOR BRAZILIAN POLITICIANS")
        print("=" * 80)
        
        # Step 1: Open Twitter and wait for login
        if not self.open_twitter_and_login():
            print("❌ Login process failed. Exiting...")
            return
        
        # Step 2: Get politicians from database
        politicians = self.get_politicians_from_database()
        
        if not politicians:
            print("❌ No politicians with Twitter profiles found in database")
            return
        
        # Step 3: Process each politician
        print(f"\n🔍 Starting tweet collection for {len(politicians)} politicians...")
        start_time = datetime.now()
        
        successful_collections = 0
        failed_collections = 0
        
        for i, politician in enumerate(politicians, 1):
            print(f"\n[{i:3d}/{len(politicians)}] Processing {politician['name']} (@{politician['username']})")
            
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
                print(f"\n⏸️  Pausing for 10 seconds (processed {i}/{len(politicians)})...")
                time.sleep(10)
        
        # Step 4: Show final results and save
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("📊 COLLECTION RESULTS SUMMARY")
        print("=" * 80)
        
        print(f"⏱️  Total time: {duration/60:.1f} minutes")
        print(f"👥 Politicians processed: {len(politicians)}")
        print(f"✅ Successful collections: {successful_collections}")
        print(f"❌ Failed collections: {failed_collections}")
        print(f"📈 Success rate: {successful_collections/len(politicians)*100:.1f}%")
        
        # Show breakdown by status
        status_counts = {}
        for result in self.collected_tweets:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n📋 Status breakdown:")
        for status, count in status_counts.items():
            print(f"   {status}: {count}")
        
        # Save results
        self.save_results_to_csv()
        
        print("=" * 80)
        
        return self.collected_tweets
    
    def cleanup(self):
        """Close the browser"""
        if self.driver:
            print("\n🔄 Closing browser...")
            self.driver.quit()
            print("✅ Browser closed")

def main():
    """Main function to run the tweet collection"""
    collector = None
    
    try:
        collector = TwitterProfileTweetCollector()
        results = collector.run_collection()
        
        print(f"\n🎉 Tweet collection complete!")
        print(f"📊 Total results: {len(results)}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
    finally:
        if collector:
            collector.cleanup()

if __name__ == "__main__":
    print("🚀 Starting Twitter Tweet Collection for Politicians...")
    print("💡 Make sure you have Chrome browser installed")
    print("💡 You'll need to manually login to Twitter/X when prompted")
    print("💡 This process may take a while depending on the number of politicians")
    
    input("\n⏳ Press ENTER to start the browser...")
    main()