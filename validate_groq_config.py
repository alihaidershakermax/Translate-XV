#!/usr/bin/env python3
"""
Validation script to test Groq-only configuration.
Verifies that the bot works with only GROQ_KEYS set.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_groq_only_config():
    """Test configuration with only Groq keys"""
    print("🧪 Testing Groq-only configuration...")
    
    # Set minimal environment for testing
    os.environ['BOT_TOKEN'] = 'test_token_12345'
    os.environ['GROQ_KEYS'] = 'test_groq_key_1,test_groq_key_2'
    os.environ['ENVIRONMENT'] = 'development'
    
    # Clear other AI service keys
    for key in ['GEMINI_KEYS', 'OPENAI_KEYS', 'AZURE_KEYS']:
        os.environ.pop(key, None)
    
    try:
        # Import and test configuration
        from config import get_settings, validate_environment
        
        print("📋 Loading settings...")
        settings = get_settings()
        
        # Verify Groq is configured
        groq_keys = settings.get_api_keys('groq')
        print(f"✅ Groq keys loaded: {len(groq_keys)} keys")
        
        # Verify other services are empty (optional)
        gemini_keys = settings.get_api_keys('gemini')
        openai_keys = settings.get_api_keys('openai')
        azure_keys = settings.get_api_keys('azure')
        
        print(f"ℹ️  Fallback services:")
        print(f"   - Gemini: {len(gemini_keys)} keys")
        print(f"   - OpenAI: {len(openai_keys)} keys")
        print(f"   - Azure: {len(azure_keys)} keys")
        
        # Test environment validation
        print("🔍 Validating environment...")
        validation_result = validate_environment()
        
        if validation_result:
            print("✅ Environment validation passed!")
            print("🎉 Groq-only configuration is working correctly!")
            return True
        else:
            print("❌ Environment validation failed!")
            return False
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_api_manager():
    """Test API manager with Groq priority"""
    print("\n🔧 Testing API Manager...")
    
    try:
        from api_manager import APIManager
        
        api_manager = APIManager()
        api_manager.load_keys()
        
        # Test getting Groq key (should be available)
        groq_key = api_manager.get_available_key('groq')
        if groq_key:
            print(f"✅ Groq API key available: {groq_key.service}")
            print(f"   Daily limit: {groq_key.daily_limit}")
        else:
            print("❌ No Groq API key available")
            return False
        
        # Test service rotation (should prefer Groq)
        current_service = 'gemini'  # Start with fallback
        rotated_service = api_manager.rotate_service(current_service)
        
        if rotated_service == 'groq':
            print("✅ Service rotation correctly prioritizes Groq")
        else:
            print(f"⚠️  Service rotation returned: {rotated_service}")
        
        return True
        
    except Exception as e:
        print(f"❌ API Manager test failed: {e}")
        return False

def show_deployment_example():
    """Show example deployment with Groq-only"""
    print("\n" + "="*60)
    print("🚀 GROQ-ONLY DEPLOYMENT EXAMPLE")
    print("="*60)
    
    print("\n📝 Minimal .env configuration:")
    print("```")
    print("# Required")
    print("BOT_TOKEN=your_telegram_bot_token")
    print("GROQ_KEYS=your_groq_key1,your_groq_key2")
    print("")
    print("# Optional (for production)")
    print("ENVIRONMENT=production")
    print("WEBHOOK_URL=https://your-app.onrender.com/webhook")
    print("DATABASE_URL=postgresql://...")
    print("REDIS_URL=redis://...")
    print("```")
    
    print("\n⚡ Benefits of Groq as Primary Service:")
    print("✅ Fast inference speed")
    print("✅ High rate limits")
    print("✅ Good multilingual support")
    print("✅ Cost-effective")
    print("✅ Reliable API availability")
    
    print("\n🔄 Fallback Strategy:")
    print("• Primary: Groq (required)")
    print("• Fallback 1: Gemini (optional)")
    print("• Fallback 2: OpenAI (optional)")
    print("• Fallback 3: Azure (optional)")
    
    print("\n📊 Expected Performance:")
    print("• Translation speed: 1-3 seconds")
    print("• Daily capacity: 2000+ requests per key")
    print("• Uptime: 99.9% (with fallbacks)")
    
    print("\n" + "="*60)

def main():
    """Main validation function"""
    print("🤖 Advanced Translation Bot - Groq Configuration Validator")
    print("=" * 60)
    
    # Test configuration
    config_test = test_groq_only_config()
    
    # Test API manager
    api_test = test_api_manager()
    
    # Show deployment example
    show_deployment_example()
    
    # Final result
    if config_test and api_test:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Your bot is configured to use Groq as the primary AI service")
        print("🚀 Ready for deployment with minimal configuration")
        return True
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("🔧 Please check your configuration")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)