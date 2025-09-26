#!/usr/bin/env python3
"""
Test script to extract Twitter info for 20 deputies
"""
import os
import sys
import django
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blindagemnao.settings')
django.setup()

# Now import after Django setup
from pressionaapp.deputados_extractor import DeputadosDataExtractor

def main():
    print("🔍 Starting Twitter extraction for 20 deputies...")
    print("=" * 60)
    
    # Initialize extractor
    extractor = DeputadosDataExtractor()
    
    try:
        # Extract deputies with social media, limit to 20
        # Enable Google fallback and Twitter-only mode for faster processing
        created_count, updated_count = extractor.extract_deputies(
            update_existing=True,
            extract_social_media=True,
            use_google_fallback=True,
            twitter_only=True,  # This parameter might not exist anymore, but keeping for compatibility
            limit=20
        )
        
        print("\n" + "=" * 60)
        print("✅ Extraction completed!")
        print(f"📊 Results:")
        print(f"   • Created: {created_count} new deputies")
        print(f"   • Updated: {updated_count} existing deputies")
        print(f"   • Total processed: {created_count + updated_count}")
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()