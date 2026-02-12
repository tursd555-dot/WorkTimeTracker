#!/usr/bin/env python3
"""
Скрипт для автоматического добавления метода get_active_session в supabase_api.py
"""
import re
from pathlib import Path

def add_get_active_session_method(file_path: str):
    """Добавляет метод get_active_session после get_all_active_sessions"""
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден!")
        return False
    
    # Читаем файл
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем, есть ли уже метод
    if 'def get_active_session(self, email: str)' in content:
        print("✅ Метод get_active_session уже существует в файле!")
        return True
    
    # Ищем место для вставки - после метода get_all_active_sessions
    pattern = r'(def get_all_active_sessions\(self\) -> List\[Dict\]:.*?return self\.get_active_sessions\(\)\s*\n\s*\n)'
    
    method_code = '''    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:
        """
        Получить активную сессию пользователя по email.
        
        Args:
            email: Email пользователя
        
        Returns:
            Словарь с данными сессии или None если не найдена
        """
        try:
            email_lower = (email or "").strip().lower()
            
            response = self.client.table('active_sessions')\\
                .select('*')\\
                .eq('email', email_lower)\\
                .eq('status', 'active')\\
                .order('login_time', desc=True)\\
                .limit(1)\\
                .execute()
            
            if response.data:
                session = response.data[0]
                # Преобразуем в формат, совместимый с sheets_api
                return {
                    'Email': session.get('email', ''),
                    'Name': session.get('name', ''),
                    'SessionID': session.get('session_id', ''),
                    'LoginTime': session.get('login_time', ''),
                    'Status': session.get('status', 'active'),
                    'LogoutTime': session.get('logout_time', ''),
                    'LogoutReason': session.get('logout_reason', ''),
                    'RemoteCommand': session.get('remote_command', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active session for {email}: {e}")
            return None
    
'''
    
    # Пытаемся найти место для вставки
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Вставляем метод после найденного места
        insert_pos = match.end()
        new_content = content[:insert_pos] + method_code + content[insert_pos:]
        print("✅ Найдено место для вставки метода")
    else:
        # Альтернативный поиск - ищем строку с return self.get_active_sessions()
        pattern2 = r'(return self\.get_active_sessions\(\)\s*\n\s*\n)'
        match2 = re.search(pattern2, content)
        
        if match2:
            insert_pos = match2.end()
            new_content = content[:insert_pos] + method_code + content[insert_pos:]
            print("✅ Найдено место для вставки метода (альтернативный поиск)")
        else:
            # Последняя попытка - найти check_user_session_status и вставить перед ним
            pattern3 = r'(def check_user_session_status\(self, email: str, session_id: str\) -> str:)'
            match3 = re.search(pattern3, content)
            
            if match3:
                insert_pos = match3.start()
                # Находим начало строки
                line_start = content.rfind('\n', 0, insert_pos) + 1
                new_content = content[:line_start] + method_code + content[line_start:]
                print("✅ Найдено место для вставки метода (перед check_user_session_status)")
            else:
                print("❌ Не удалось найти место для вставки метода!")
                print("   Попробуйте добавить метод вручную после метода get_all_active_sessions()")
                return False
    
    # Создаем резервную копию
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"📦 Создана резервная копия: {backup_path}")
    
    # Записываем обновленный файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Метод get_active_session успешно добавлен в {file_path}")
    return True

if __name__ == "__main__":
    import sys
    
    # Путь к файлу (по умолчанию текущая директория)
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "supabase_api.py"
    
    print(f"🔧 Добавление метода get_active_session в {file_path}...")
    print()
    
    success = add_get_active_session_method(file_path)
    
    if success:
        print()
        print("✅ Готово! Теперь можно запустить приложение:")
        print("   python user_app/main.py")
    else:
        print()
        print("❌ Не удалось добавить метод автоматически.")
        print("   Добавьте метод вручную в VS Code.")
    
    sys.exit(0 if success else 1)
