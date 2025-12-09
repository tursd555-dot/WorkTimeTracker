# coding: utf-8
import os, re, shutil
from datetime import datetime
from pathlib import Path

file_path = Path("admin_app/break_schedule_dialog.py")
if not file_path.exists():
    print("ERROR: File not found")
    exit(1)

# Backup
backup = file_path.with_suffix(f'.py.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
shutil.copy2(file_path, backup)
print(f"OK: Backup created: {backup}")

# Read
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Check if already patched
if '_generate_schedule_id' in content:
    print("WARNING: Already patched!")
    exit(0)

# Patch imports
if 'import re' not in content:
    content = content.replace('from typing import', 'import re\nfrom datetime import datetime\nfrom typing import')
    print("OK: 1. Imports added")

# Patch button
button_code = '''
        
        # NEW: Auto-generate ID button
        btn_generate_id = QPushButton("Generate ID")
        btn_generate_id.setToolTip("Auto-generate unique ID")
        btn_generate_id.clicked.connect(self._generate_schedule_id)
        btn_generate_id.setMaximumWidth(130)
        id_row.addWidget(btn_generate_id)'''

content = content.replace(
    'id_row.addWidget(self.schedule_id_input)',
    'id_row.addWidget(self.schedule_id_input)' + button_code
)
print("OK: 2. Button added")

# Patch methods
methods = '''
    
    def _generate_schedule_id(self):
        name = self.name_input.text().strip()
        if name:
            generated_id = self._generate_id_from_name(name)
        else:
            shift_start = self.shift_start_input.time().toString("HHmm")
            shift_end = self.shift_end_input.time().toString("HHmm")
            generated_id = f"SHIFT_{shift_start}_{shift_end}"
        self.schedule_id_input.setText(generated_id)
        self.schedule_id_input.setFocus()
        self.schedule_id_input.selectAll()
    
    def _generate_id_from_name(self, name: str) -> str:
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        result = []
        for char in name.lower():
            if char in translit_map:
                result.append(translit_map[char])
            elif char.isalnum():
                result.append(char)
            elif char in (' ', '-', '/', '(', ')'):
                result.append('_')
        generated = ''.join(result)
        generated = re.sub(r'_+', '_', generated)
        generated = generated.strip('_').upper()
        if len(generated) > 30:
            generated = generated[:30]
        return generated or "SCHEDULE"
'''

content = content.replace('    def _load_data(self):', methods + '\n    def _load_data(self):')
print("OK: 3. Methods added")

# Save
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: Patch applied!")
print("NEXT: Restart admin_app")
