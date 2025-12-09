#!/usr/bin/env python3
"""
Патч для добавления метода get_fresh_unsynced_actions в db_local.py
"""

import sys
from pathlib import Path

def apply_patch():
    db_local_path = Path("user_app/db_local.py")
    
    if not db_local_path.exists():
        print(f"❌ Файл не найден: {db_local_path}")
        return False
    
    # Читаем файл
    with open(db_local_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Новый метод
    new_method = '''
    def get_fresh_unsynced_actions(self, age_minutes: int = 5, limit: int = 50) -> List[Tuple]:
        """
        Получить СВЕЖИЕ несинхронизированные записи (приоритет для offline recovery).
        
        Args:
            age_minutes: Возраст записей в минутах (по умолчанию 5)
            limit: Максимальное количество записей
            
        Returns:
            Список свежих несинхронизированных записей
        """
        self._ensure_open()
        if self.conn is None:
            return []
        
        with self._lock:
            with read_cursor() as cur:
                # Вычисляем timestamp для фильтрации
                from datetime import datetime, timedelta
                cutoff_time = (datetime.now() - timedelta(minutes=age_minutes)).isoformat()
                
                cur.execute(
                    """
                    SELECT id, email, name, status, action_type, comment, timestamp,
                           session_id, status_start_time, status_end_time, reason, user_group
                      FROM logs
                     WHERE synced = 0
                       AND timestamp >= ?
                  ORDER BY priority DESC, timestamp ASC
                     LIMIT ?
                    """,
                    (cutoff_time, int(limit)),
                )
                return list(cur.fetchall())
'''
    
    # Ищем место для вставки (после get_unsynced_actions)
    marker = "    def get_unsynced_count(self) -> int:"
    
    if marker not in content:
        print(f"❌ Маркер не найден в файле")
        return False
    
    # Вставляем новый метод
    content = content.replace(marker, new_method + "\n" + marker)
    
    # Записываем обратно
    with open(db_local_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Метод get_fresh_unsynced_actions добавлен в db_local.py")
    return True

if __name__ == "__main__":
    if apply_patch():
        sys.exit(0)
    else:
        sys.exit(1)
