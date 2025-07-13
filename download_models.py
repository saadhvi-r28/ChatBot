#!/usr/bin/env python3
"""
Script to download faster models for the chatbot
Run this script to download the recommended models for better performance
"""

import subprocess
import sys
import time

def run_command(command, description):
    """Run a command and show progress"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("🚀 Chatbot Model Downloader")
    print("=" * 40)
    print("This script will download faster models for your chatbot.")
    print("Recommended models for better performance:")
    print("• llama3.2:1b - Fastest (smallest)")
    print("• llama3.2:3b - Balanced (recommended)")
    print("• deepseek-r1:8b - Your current model")
    
    # Check if Ollama is running
    print("\n🔍 Checking if Ollama is running...")
    try:
        subprocess.run(["ollama", "list"], check=True, capture_output=True)
        print("✅ Ollama is running!")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Ollama is not running or not installed!")
        print("Please start Ollama first: ollama serve")
        return

    # Models to download (in order of preference)
    models = [
        ("llama3.2:1b", "Llama 3.2 1B (Fastest - Smaller Context)"),
        ("llama3.2:3b", "Llama 3.2 3B (Recommended - Fast & Good Quality)"),
        ("deepseek-r1:8b","Deepseek-r1 8B (Balanced- Good Quality)")
    ]
    
    print(f"\n📥 Will download {len(models)} models...")
    print("This may take several minutes depending on your internet connection.")
    
    for model_name, description in models:
        print(f"\n{'='*50}")
        print(f"📦 {description}")
        print(f"Model: {model_name}")
        
        # Check if model already exists
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if model_name in result.stdout:
                print(f"✅ {model_name} already exists, skipping...")
                continue
        except:
            pass
        
        # Download the model
        if run_command(f"ollama pull {model_name}", f"Downloading {model_name}"):
            print(f"🎉 {model_name} downloaded successfully!")
        else:
            print(f"⚠️  Failed to download {model_name}, continuing with next model...")
        
        # Small delay between downloads
        time.sleep(2)
    
    print(f"\n{'='*50}")
    print("🎉 Model download process completed!")
    print("\n📋 Next steps:")
    print("1. Start your chatbot: python app.py")
    print("2. Run the chatbot with frontend: npm start")
    print("3. In the sidebar, select 'Fast (3B)' for best performance")
    print("4. Adjust the 'Max Response Length' slider to 100-1000 for faster replies")
    print("5. Use the 'Clear Chat' button periodically to free up memory")

if __name__ == "__main__":
    main() 