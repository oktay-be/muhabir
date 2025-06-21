#!/usr/bin/env python3
"""
Migration script for AISports refactoring.
This script helps set up the new architecture and migrate from custom scraping to journ4list.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_step(step_num, description):
    """Print a formatted step description."""
    print(f"\n🔄 Step {step_num}: {description}")
    print("-" * 50)

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - Success")
        if result.stdout:
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed")
        print(f"Error: {e.stderr.strip()}")
        return False

def create_directory_structure():
    """Create the new directory structure."""
    directories = [
        "capabilities/services",
        "integrations", 
        "api/endpoints",
        "config",
        ".archive/deprecated_scraping",
        ".archive/deprecated_tests",
        "tests/services",
        "tests/endpoints"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    return True

def backup_existing_code():
    """Backup existing scraping code to archive."""
    if os.path.exists("capabilities/scraping"):
        try:
            # Copy to archive
            shutil.copytree("capabilities/scraping", ".archive/deprecated_scraping", dirs_exist_ok=True)
            print("✅ Backed up scraping code to .archive/deprecated_scraping")
            
            # List what was backed up
            backup_files = list(Path(".archive/deprecated_scraping").rglob("*.py"))
            print(f"📦 Backed up {len(backup_files)} Python files")
            
            return True
        except Exception as e:
            print(f"❌ Failed to backup scraping code: {e}")
            return False
    else:
        print("ℹ️  No existing scraping directory found")
        return True

def install_dependencies():
    """Install journ4list and other new dependencies."""
    dependencies = [
        "journ4list>=0.1.0"
    ]
    
    for dep in dependencies:
        if run_command(f"pip install {dep}", f"Installing {dep}"):
            continue
        else:
            return False
    
    return True

def create_init_files():
    """Create __init__.py files for new packages."""
    init_files = [
        "capabilities/services/__init__.py",
        "integrations/__init__.py", 
        "api/endpoints/__init__.py"
    ]
    
    for init_file in init_files:
        with open(init_file, 'w') as f:
            f.write(f'"""Module: {os.path.dirname(init_file)}"""\n')
        print(f"📄 Created: {init_file}")
    
    return True

def update_requirements():
    """Update requirements.txt with new dependencies."""
    new_deps = [
        "journ4list>=0.1.0"
    ]
    
    try:
        # Read existing requirements
        existing_deps = []
        if os.path.exists("requirements.txt"):
            with open("requirements.txt", 'r') as f:
                existing_deps = f.read().splitlines()
        
        # Add new dependencies if not already present
        updated = False
        for dep in new_deps:
            dep_name = dep.split(">=")[0].split("==")[0]
            if not any(dep_name in line for line in existing_deps):
                existing_deps.append(dep)
                updated = True
        
        if updated:
            with open("requirements.txt", 'w') as f:
                f.write("\n".join(existing_deps) + "\n")
            print("✅ Updated requirements.txt")
        else:
            print("ℹ️  requirements.txt already up to date")
            
        return True
    except Exception as e:
        print(f"❌ Failed to update requirements.txt: {e}")
        return False

def create_sample_config():
    """Create sample configuration files."""
    
    # Create scraping config
    scraping_config = {
        "journ4list": {
            "default_persist": True,
            "default_scrape_depth": 2,
            "workspace_cleanup_hours": 24,
            "max_concurrent_sessions": 5
        },
        "extraction": {
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "user_agent": "AISports-Bot/2.0"
        }
    }
    
    with open("config/scraping_config.json", 'w') as f:
        import json
        json.dump(scraping_config, f, indent=2)
    print("📄 Created config/scraping_config.json")
    
    # Create .env template
    env_template = """# AISports Configuration

# Existing API Keys (keep your values)
GOOGLE_API_KEY=your_google_api_key_here
NEWSAPI_KEY=your_newsapi_key_here
WORLDNEWSAPI_KEY=your_worldnews_key_here

# New journ4list Configuration
JOURN4LIST_WORKSPACE_DIR=.journalist_workspace
JOURN4LIST_DEFAULT_PERSIST=true
JOURN4LIST_DEFAULT_SCRAPE_DEPTH=2

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=true
"""
    
    if not os.path.exists(".env"):
        with open(".env.template", 'w') as f:
            f.write(env_template)
        print("📄 Created .env.template (copy to .env and update with your keys)")
    else:
        print("ℹ️  .env already exists, skipping template creation")
    
    return True

def run_migration():
    """Run the complete migration process."""
    print("🚀 Starting AISports Refactoring Migration")
    print("=" * 60)
    
    steps = [
        (1, "Creating directory structure", create_directory_structure),
        (2, "Backing up existing code", backup_existing_code),
        (3, "Installing dependencies", install_dependencies),
        (4, "Creating __init__.py files", create_init_files),
        (5, "Updating requirements.txt", update_requirements),
        (6, "Creating sample configuration", create_sample_config)
    ]
    
    failed_steps = []
    
    for step_num, description, func in steps:
        print_step(step_num, description)
        try:
            if func():
                print(f"✅ Step {step_num} completed successfully")
            else:
                print(f"❌ Step {step_num} failed")
                failed_steps.append(step_num)
        except Exception as e:
            print(f"❌ Step {step_num} failed with exception: {e}")
            failed_steps.append(step_num)
    
    print("\n" + "=" * 60)
    if failed_steps:
        print(f"⚠️  Migration completed with {len(failed_steps)} failed steps: {failed_steps}")
        print("Please review the errors above and fix manually.")
    else:
        print("🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Update your .env file with API keys")
        print("2. Review the backup in .archive/deprecated_scraping")
        print("3. Test the new architecture with test_new_architecture.py")
        print("4. Implement the services from IMPLEMENTATION_PLAN.md")
    
    print("\n📚 Documentation:")
    print("- Full plan: .archive/REFACTORING_PLAN.md")
    print("- Implementation guide: .archive/IMPLEMENTATION_PLAN.md")

if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("capabilities") or not os.path.exists("api"):
        print("❌ Please run this script from the AISports project root directory")
        sys.exit(1)
    
    run_migration()
