import os
import glob

# Паттерн для замены
OLD = "from api_adapter import"
NEW = "from api_adapter import"

# Найти все Python файлы
files = glob.glob("**/*.py", recursive=True)

updated = []
for filepath in files:
    # Пропускаем сам api_adapter.py и sheets_api.py
    if "api_adapter.py" in filepath or "sheets_api.py" in filepath:
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if OLD in content:
            new_content = content.replace(OLD, NEW)
            
            with open(filepath, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write(new_content)
            
            updated.append(filepath)
            print(f"✅ Updated: {filepath}")
    
    except Exception as e:
        print(f"❌ Error in {filepath}: {e}")

print(f"\n✅ Updated {len(updated)} files")