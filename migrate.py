#!/usr/bin/env python3
"""
Migration script to update the existing bot to the new optimized version.
This script safely backs up the old version and replaces it with the new one.
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

def migrate_to_optimized_version():
    """Migrate from old main.py to the new optimized version"""
    
    print("🔄 Starting migration to optimized bot version...")
    
    # Get the current directory
    current_dir = Path(__file__).parent
    old_main = current_dir / "main.py"
    new_main = current_dir / "main_optimized.py"
    startup_script = current_dir / "start_bot.py"
    
    # Check if files exist
    if not new_main.exists():
        print("❌ Error: main_optimized.py not found!")
        return False
    
    if not startup_script.exists():
        print("❌ Error: start_bot.py not found!")
        return False
    
    # Create backup directory
    backup_dir = current_dir / "backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup existing files
    if old_main.exists():
        backup_path = backup_dir / "main.py.bak"
        shutil.copy2(old_main, backup_path)
        print(f"✅ Backed up old main.py to {backup_path}")
    
    # Replace main.py with optimized version
    try:
        if old_main.exists():
            old_main.unlink()  # Delete old main.py
        
        shutil.copy2(new_main, old_main)  # Copy optimized version
        print("✅ Replaced main.py with optimized version")
        
        # Make start_bot.py executable
        startup_script.chmod(0o755)
        print("✅ Made start_bot.py executable")
        
        # Create a simple migration marker
        migration_marker = current_dir / ".migration_completed"
        migration_marker.write_text(f"Migrated to optimized version on {datetime.now().isoformat()}")
        
        print("\n🎉 Migration completed successfully!")
        print("\n📋 Next steps:")
        print("1. Update your environment variables (see .env.example)")
        print("2. Test locally: python start_bot.py")
        print("3. Deploy to production with the new configuration")
        print("4. Monitor health endpoints after deployment")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        
        # Restore backup if available
        if old_main.exists() and (backup_dir / "main.py.bak").exists():
            shutil.copy2(backup_dir / "main.py.bak", old_main)
            print("🔄 Restored backup")
        
        return False

def verify_migration():
    """Verify that the migration was successful"""
    
    print("🔍 Verifying migration...")
    
    current_dir = Path(__file__).parent
    
    # Check required files
    required_files = [
        "main.py",
        "start_bot.py", 
        "config.py",
        "cache_system.py",
        "database.py",
        "monitoring.py",
        "health_server.py",
        "security.py",
        "render.yaml",
        "Dockerfile",
        "pyproject.toml"
    ]
    
    missing_files = []
    for file_name in required_files:
        if not (current_dir / file_name).exists():
            missing_files.append(file_name)
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return False
    
    # Check that main.py contains optimized content
    main_content = (current_dir / "main.py").read_text()
    if "OptimizedTranslationBot" not in main_content:
        print("❌ main.py doesn't contain optimized bot code")
        return False
    
    print("✅ All required files present")
    print("✅ main.py contains optimized code")
    print("✅ Migration verification successful!")
    
    return True

def show_deployment_info():
    """Show deployment information"""
    
    print("\n" + "="*60)
    print("🚀 READY FOR DEPLOYMENT!")
    print("="*60)
    
    print("\n📦 New Features Added:")
    print("✅ Advanced caching system (Redis + memory)")
    print("✅ Database integration (PostgreSQL)")
    print("✅ Comprehensive monitoring & logging")
    print("✅ Health check endpoints")
    print("✅ Security & rate limiting")
    print("✅ Performance optimizations")
    print("✅ Production-ready configuration")
    
    print("\n🔧 Configuration Required:")
    print("1. Copy .env.example to .env")
    print("2. Set your BOT_TOKEN")
    print("3. Add AI API keys (Gemini, OpenAI, etc.)")
    print("4. Configure webhook URL for production")
    
    print("\n📊 Monitoring Endpoints:")
    print("• Health: /health")
    print("• Metrics: /metrics") 
    print("• Status: /status")
    print("• Logs: /logs")
    
    print("\n🌐 Deployment Options:")
    print("• Local: python start_bot.py")
    print("• Render.com: Use render.yaml (automatic)")
    print("• Docker: Use Dockerfile")
    
    print("\n📖 Documentation:")
    print("• README.md - Complete project overview")
    print("• DEPLOYMENT_GUIDE.md - Step-by-step deployment")
    print("• .env.example - Configuration template")
    
    print("\n" + "="*60)

def main():
    """Main migration function"""
    
    print("🤖 Advanced Translation Bot - Migration Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        success = verify_migration()
        sys.exit(0 if success else 1)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        show_deployment_info()
        sys.exit(0)
    
    # Check if already migrated
    current_dir = Path(__file__).parent
    migration_marker = current_dir / ".migration_completed"
    
    if migration_marker.exists():
        print("✅ Migration already completed!")
        print(f"Migration date: {migration_marker.read_text().strip()}")
        
        if input("\n🔄 Force re-migration? (y/N): ").lower() != 'y':
            print("Migration cancelled.")
            show_deployment_info()
            return
    
    # Perform migration
    success = migrate_to_optimized_version()
    
    if success:
        # Verify migration
        verify_migration()
        show_deployment_info()
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()