#!/usr/bin/env python3
"""
Test script to validate OptimizedTranslationBot initialization
"""

import sys
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_bot_initialization():
    """Test bot initialization without running it"""
    try:
        # Import the bot class
        from main_optimized import OptimizedTranslationBot
        
        # Create bot instance
        logger.info("🤖 Creating OptimizedTranslationBot instance...")
        bot = OptimizedTranslationBot()
        
        # Check that all required attributes exist
        required_attributes = [
            'help_command', 'status_command', 'stats_command', 
            'button_callback', 'handle_photo', 'handle_text', 'handle_document'
        ]
        
        missing_attributes = []
        for attr in required_attributes:
            if not hasattr(bot, attr):
                missing_attributes.append(attr)
        
        if missing_attributes:
            logger.error(f"❌ Missing attributes: {missing_attributes}")
            return False
        else:
            logger.info("✅ All required command methods are present")
        
        # Check that methods are callable
        for attr in required_attributes:
            method = getattr(bot, attr)
            if not callable(method):
                logger.error(f"❌ {attr} is not callable")
                return False
        
        logger.info("✅ All command methods are callable")
        logger.info("🎉 Bot initialization test passed!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting OptimizedTranslationBot initialization test...")
    
    success = test_bot_initialization()
    
    if success:
        logger.info("✅ Test completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Test failed!")
        sys.exit(1)