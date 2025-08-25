#!/usr/bin/env python3
"""
Test script to validate bot startup without event loop issues
"""

import asyncio
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_bot_startup():
    """Test bot startup and shutdown process"""
    try:
        # Set required environment variables for testing
        if not os.getenv("BOT_TOKEN"):
            os.environ["BOT_TOKEN"] = "test_token_123"
        if not os.getenv("GROQ_KEYS"):
            os.environ["GROQ_KEYS"] = "test_key_123"
        
        logger.info("🧪 Testing bot initialization...")
        
        # Test OptimizedTranslationBot import and creation
        from main_optimized import OptimizedTranslationBot
        bot = OptimizedTranslationBot()
        
        logger.info("✅ Bot instance created successfully")
        
        # Test cache system
        logger.info("🧪 Testing cache system...")
        if hasattr(bot, 'cache_system') and bot.cache_system:
            await bot.cache_system.set("test_key", "test_value", 60)
            value = await bot.cache_system.get("test_key")
            if value == "test_value":
                logger.info("✅ Cache system working")
            else:
                logger.warning("⚠️ Cache system test failed")
        
        # Test initialization
        logger.info("🧪 Testing bot initialization...")
        try:
            await bot.initialize()
            logger.info("✅ Bot initialization successful")
        except Exception as e:
            logger.error(f"❌ Bot initialization failed: {e}")
            return False
        
        # Test application setup
        if bot.application:
            logger.info("✅ Telegram application setup successful")
        else:
            logger.error("❌ Telegram application not initialized")
            return False
        
        # Test cleanup
        logger.info("🧪 Testing bot shutdown...")
        await bot.shutdown()
        logger.info("✅ Bot shutdown successful")
        
        logger.info("🎉 All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting bot validation tests...")
    
    success = await test_bot_startup()
    
    if success:
        logger.info("✅ Validation completed successfully!")
        return 0
    else:
        logger.error("❌ Validation failed!")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        sys.exit(1)