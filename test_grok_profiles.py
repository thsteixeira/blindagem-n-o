#!/usr/bin/env python
"""
Simple test script to test Grok API profile discovery for specific politicians
"""

import os
import sys
import django
from django.conf import settings

# Add the project path to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pressiona.settings')
django.setup()

from pressionaapp.grok_service import GrokTwitterService, GrokAPIError

def test_profile_discovery():
    """Test Grok API with known politicians and their correct Twitter profiles"""
    
    # Test cases with known correct profiles
    test_cases = [
        {
            "nome": "José Afonso Ebert Hamm",
            "nome_parlamentar": "Afonso Hamm", 
            "role": "deputado",
            "additional_context": "partido PP estado RS",
            "expected": "@DepAfonsoHamm",
            "expected_clean": "DepAfonsoHamm"
        },
        {
            "nome": "Antonio José de Albuquerque",
            "nome_parlamentar": "AJ Albuquerque",
            "role": "deputado", 
            "additional_context": "partido PDT estado CE",
            "expected": "@albuquerque_aj",
            "expected_clean": "albuquerque_aj"
        },
        {
            "nome": "Adolfo Viana Netto",
            "nome_parlamentar": "Adolfo Viana",
            "role": "deputado",
            "additional_context": "partido PSDB estado BA", 
            "expected": "@AdolfoViana_",
            "expected_clean": "AdolfoViana_"
        },
        {
            "nome": "José Guimarães Neumann Neto",
            "nome_parlamentar": "Albuquerque",
            "role": "deputado",
            "additional_context": "partido PSB estado RR",
            "expected": "@albuquerque2022", 
            "expected_clean": "albuquerque2022"
        }
    ]
    
    print("🧪 Testing Grok Twitter Profile Discovery")
    print("=" * 60)
    
    try:
        # Initialize Grok service
        grok_service = GrokTwitterService()
        print("✅ Grok service initialized successfully")
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 Test {i}: {test_case['nome_parlamentar']}")
            print(f"   Full name: {test_case['nome']}")
            print(f"   Expected: {test_case['expected']}")
            print(f"   Context: {test_case['additional_context']}")
            
            try:
                # Call Grok API
                profile_result = grok_service.find_twitter_profile(
                    nome=test_case['nome'],
                    nome_parlamentar=test_case['nome_parlamentar'],
                    role=test_case['role'],
                    additional_context=test_case['additional_context']
                )
                
                if profile_result:
                    found_url = profile_result.get('url', '')
                    found_username = profile_result.get('username', '')
                    confidence = profile_result.get('confidence_score', 0)
                    
                    # Check if result matches expected
                    is_correct = (
                        test_case['expected_clean'] in found_url or 
                        test_case['expected_clean'] == found_username
                    )
                    
                    status = "✅ CORRECT" if is_correct else "❌ INCORRECT" 
                    
                    print(f"   Result: {found_url}")
                    print(f"   Username: @{found_username}")
                    print(f"   Confidence: {confidence:.2f}")
                    print(f"   Status: {status}")
                    
                    results.append({
                        'name': test_case['nome_parlamentar'],
                        'expected': test_case['expected'],
                        'found': f"@{found_username}" if found_username else found_url,
                        'correct': is_correct,
                        'confidence': confidence
                    })
                    
                else:
                    print("   Result: ❌ No profile found")
                    results.append({
                        'name': test_case['nome_parlamentar'],
                        'expected': test_case['expected'],
                        'found': "NOT_FOUND",
                        'correct': False,
                        'confidence': 0.0
                    })
                    
            except GrokAPIError as e:
                print(f"   ❌ Grok API Error: {e}")
                results.append({
                    'name': test_case['nome_parlamentar'],
                    'expected': test_case['expected'],
                    'found': f"API_ERROR: {e}",
                    'correct': False,
                    'confidence': 0.0
                })
                
            except Exception as e:
                print(f"   ❌ Unexpected Error: {e}")
                results.append({
                    'name': test_case['nome_parlamentar'],
                    'expected': test_case['expected'],
                    'found': f"ERROR: {e}",
                    'correct': False,
                    'confidence': 0.0
                })
        
        # Summary report
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        correct_count = sum(1 for r in results if r['correct'])
        total_count = len(results)
        accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0
        
        print(f"Total tests: {total_count}")
        print(f"Correct results: {correct_count}")
        print(f"Accuracy: {accuracy:.1f}%")
        
        print("\nDetailed Results:")
        for result in results:
            status_icon = "✅" if result['correct'] else "❌"
            print(f"{status_icon} {result['name']:<15} | Expected: {result['expected']:<20} | Found: {result['found']:<20} | Conf: {result['confidence']:.2f}")
        
        if accuracy < 100:
            print(f"\n⚠️  {total_count - correct_count} profiles need attention")
            print("Consider adjusting the Grok prompts for better accuracy")
        else:
            print("\n🎉 Perfect accuracy! All profiles found correctly")
            
    except Exception as e:
        print(f"❌ Failed to initialize Grok service: {e}")
        print("Make sure GROK_API_KEY is set in your environment")

if __name__ == "__main__":
    test_profile_discovery()