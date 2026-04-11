import json

def load_config():
    print("⚙️ Loading system configuration from config.json...")
    
    # This will throw FileNotFoundError if the file doesn't exist.
    # If the file is just created empty (e.g. via touch), it will throw a JSONDecodeError!
    with open("config.json", "r") as f:
        config = json.load(f)
        
    print("✅ Config loaded successfully!")
    print(config)

if __name__ == "__main__":
    load_config()
