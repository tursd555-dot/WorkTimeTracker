"""
Conflict Resolution System for WorkTimeTracker Sync

Система разрешения конфликтов при синхронизации между локальной БД и Google Sheets.

Проблема:
Пользователь меняет статус → сохраняется локально → интернет пропадает →
Администратор меняет данные в Google Sheets → интернет возвращается →
КОНФЛИКТ: локальная версия ≠ удаленная версия

Решение:
Умные стратегии разрешения конфликтов с сохранением истории.

Стратегии разрешения:
- LAST_WRITE_WINS: Последняя запись побеждает (по timestamp)
- ADMIN_WINS: Приоритет у администратора
- USER_WINS: Приоритет у пользователя
- MERGE: Умное слияние изменений
- MANUAL: Требуется ручное разрешение

Использование:
    from sync.conflict_resolver import ConflictResolver, ConflictInfo
    
    resolver = ConflictResolver(strategy='last_write_wins')
    
    conflict = ConflictInfo(
        local_record={'status': 'Обед', 'timestamp': '2025-11-24T10:00:00'},
        remote_record={'status': 'В работе', 'timestamp': '2025-11-24T10:05:00'},
        entity_type='STATUS_CHANGE',
        entity_id='user@example.com'
    )
    
    try:
        winner = resolver.resolve(conflict)
        # Применить winner к обеим сторонам
    except ConflictRequiresManualResolution:
        # Показать пользователю/админу диалог выбора
        pass

Автор: WorkTimeTracker Sync Team
Дата: 2025-11-24
"""

import logging
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class ConflictResolutionStrategy(Enum):
    """
    Стратегии разрешения конфликтов.
    
    Attributes:
        LAST_WRITE_WINS: Последняя запись побеждает (по timestamp)
        ADMIN_WINS: Администратор всегда прав
        USER_WINS: Пользователь всегда прав
        MERGE: Попытка умного слияния изменений
        MANUAL: Требуется ручное разрешение
    """
    LAST_WRITE_WINS = "last_write_wins"
    ADMIN_WINS = "admin_wins"
    USER_WINS = "user_wins"
    MERGE = "merge"
    MANUAL = "manual"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ConflictInfo:
    """
    Информация о конфликте между локальной и удаленной записью.
    
    Attributes:
        local_record: Локальная версия записи
        remote_record: Удаленная версия записи (из Google Sheets)
        local_timestamp: Время последнего изменения локально
        remote_timestamp: Время последнего изменения удаленно
        entity_type: Тип сущности (STATUS_CHANGE, LOGIN, etc.)
        entity_id: ID сущности (обычно email пользователя)
    """
    local_record: Dict[str, Any]
    remote_record: Dict[str, Any]
    local_timestamp: datetime
    remote_timestamp: datetime
    entity_type: str
    entity_id: str
    
    def __str__(self):
        return (
            f"Conflict({self.entity_type}:{self.entity_id}, "
            f"local={self.local_timestamp}, remote={self.remote_timestamp})"
        )


@dataclass
class ConflictResolution:
    """
    Результат разрешения конфликта.
    
    Attributes:
        winner: Финальная версия записи
        strategy_used: Использованная стратегия
        changes_made: Список сделанных изменений
        timestamp: Время разрешения конфликта
    """
    winner: Dict[str, Any]
    strategy_used: str
    changes_made: List[str]
    timestamp: datetime


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ConflictRequiresManualResolution(Exception):
    """
    Конфликт требует ручного вмешательства.
    
    Attributes:
        conflict: Информация о конфликте
    """
    def __init__(self, conflict: ConflictInfo):
        self.conflict = conflict
        super().__init__(
            f"Manual resolution required for {conflict.entity_type}:{conflict.entity_id}"
        )


# ============================================================================
# CONFLICT RESOLVER
# ============================================================================

class ConflictResolver:
    """
    Resolver для конфликтов синхронизации.
    
    Автоматически разрешает конфликты между локальной БД и Google Sheets
    на основе выбранной стратегии.
    
    Использование:
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.LAST_WRITE_WINS)
        
        try:
            winner = resolver.resolve(conflict_info)
            # Применить winner к обеим сторонам (local и remote)
            apply_to_local(winner)
            apply_to_remote(winner)
        except ConflictRequiresManualResolution as e:
            # Показать UI для ручного выбора
            winner = show_conflict_dialog(e.conflict)
            apply_resolution(winner)
    
    Attributes:
        strategy: Текущая стратегия разрешения
        conflict_log: История разрешенных конфликтов
    """
    
    def __init__(
        self,
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS
    ):
        """
        Инициализация resolver.
        
        Args:
            strategy: Стратегия разрешения конфликтов
        """
        self.strategy = strategy
        self.conflict_log: List[Dict[str, Any]] = []
    
    def resolve(self, conflict: ConflictInfo) -> Dict[str, Any]:
        """
        Разрешить конфликт и вернуть финальное состояние.
        
        Args:
            conflict: Информация о конфликте
            
        Returns:
            Финальная версия записи (winner)
            
        Raises:
            ConflictRequiresManualResolution: Если нужно ручное решение
        """
        logger.info(
            f"Resolving conflict for {conflict.entity_type}:{conflict.entity_id} "
            f"using strategy {self.strategy.value}"
        )
        
        # Применить выбранную стратегию
        if self.strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            winner = self._last_write_wins(conflict)
            changes = ["Selected record with newest timestamp"]
            
        elif self.strategy == ConflictResolutionStrategy.ADMIN_WINS:
            winner = self._admin_wins(conflict)
            changes = ["Admin changes take priority"]
            
        elif self.strategy == ConflictResolutionStrategy.USER_WINS:
            winner = self._user_wins(conflict)
            changes = ["User changes take priority"]
            
        elif self.strategy == ConflictResolutionStrategy.MERGE:
            winner, changes = self._merge(conflict)
            
        else:  # MANUAL
            raise ConflictRequiresManualResolution(conflict)
        
        # Залогировать решение
        self._log_resolution(conflict, winner, changes)
        
        return winner
    
    def _last_write_wins(self, conflict: ConflictInfo) -> Dict[str, Any]:
        """
        Стратегия: Последняя запись побеждает.
        
        Сравнивает timestamp'ы и выбирает более новую запись.
        """
        if conflict.remote_timestamp > conflict.local_timestamp:
            logger.info("Remote wins (newer timestamp)")
            return conflict.remote_record.copy()
        else:
            logger.info("Local wins (newer timestamp)")
            return conflict.local_record.copy()
    
    def _admin_wins(self, conflict: ConflictInfo) -> Dict[str, Any]:
        """
        Стратегия: Администратор всегда прав.
        
        Remote запись считается изменением от администратора.
        """
        # Проверяем, есть ли признак изменения администратором
        if conflict.remote_record.get('modified_by') == 'admin':
            logger.info("Remote wins (admin modified)")
            return conflict.remote_record.copy()
        
        # Если нет явного признака, считаем remote = admin изменения
        logger.info("Remote wins (assumed admin priority)")
        return conflict.remote_record.copy()
    
    def _user_wins(self, conflict: ConflictInfo) -> Dict[str, Any]:
        """
        Стратегия: Пользователь всегда прав.
        
        Local запись имеет приоритет.
        """
        logger.info("Local wins (user priority)")
        return conflict.local_record.copy()
    
    def _merge(self, conflict: ConflictInfo) -> tuple[Dict[str, Any], List[str]]:
        """
        Стратегия: Умное слияние записей.
        
        Алгоритм:
        1. Базовые поля (id, email) - из любой записи (не конфликтуют)
        2. Timestamp поля - последний из двух
        3. Статус - из записи с более поздним timestamp
        4. Комментарий - объединить, если разные
        5. Остальные поля - last write wins
        
        Returns:
            Tuple[merged_record, list_of_changes]
        """
        merged = conflict.local_record.copy()
        changes = []
        
        for key, remote_value in conflict.remote_record.items():
            local_value = merged.get(key)
            
            # Если значения одинаковые - нет конфликта
            if local_value == remote_value:
                continue
            
            # Специальная обработка для timestamp полей
            if key in ['timestamp', 'last_modified', 'status_start_time', 
                      'status_end_time', 'login_time', 'logout_time']:
                try:
                    local_dt = self._parse_datetime(local_value)
                    remote_dt = self._parse_datetime(remote_value)
                    
                    if remote_dt > local_dt:
                        merged[key] = remote_value
                        changes.append(f"Updated {key} to remote (newer)")
                    else:
                        changes.append(f"Kept local {key} (newer)")
                except:
                    # Если парсинг не удался - берем remote
                    merged[key] = remote_value
                    changes.append(f"Updated {key} to remote (parse error)")
            
            # Специальная обработка для статуса
            elif key == 'status':
                local_modified = self._parse_datetime(
                    conflict.local_record.get('last_modified', '1970-01-01T00:00:00')
                )
                remote_modified = self._parse_datetime(
                    conflict.remote_record.get('last_modified', '1970-01-01T00:00:00')
                )
                
                if remote_modified > local_modified:
                    merged[key] = remote_value
                    changes.append(f"Updated status to '{remote_value}' (remote newer)")
                else:
                    changes.append(f"Kept local status '{local_value}' (local newer)")
            
            # Специальная обработка для комментария
            elif key == 'comment':
                if local_value and remote_value and local_value != remote_value:
                    # Объединить комментарии
                    merged[key] = f"{local_value} | [Remote: {remote_value}]"
                    changes.append("Merged comments from both sources")
                elif remote_value:
                    merged[key] = remote_value
                    changes.append("Updated comment to remote")
                else:
                    changes.append("Kept local comment")
            
            # Для остальных полей - last write wins
            else:
                if conflict.remote_timestamp > conflict.local_timestamp:
                    merged[key] = remote_value
                    changes.append(f"Updated {key} to remote (newer record)")
                else:
                    changes.append(f"Kept local {key} (newer record)")
        
        logger.info(f"Merged record with {len(changes)} changes")
        return merged, changes
    
    def _parse_datetime(self, value: Any) -> datetime:
        """
        Парсинг datetime из различных форматов.
        
        Args:
            value: Значение для парсинга (str, datetime, или None)
            
        Returns:
            datetime объект
        """
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            # ISO format: 2025-11-24T10:00:00 или с timezone
            try:
                # Убрать timezone info если есть
                if '+' in value:
                    value = value.split('+')[0]
                if 'Z' in value:
                    value = value.replace('Z', '')
                
                return datetime.fromisoformat(value)
            except:
                pass
        
        # Fallback - минимальная дата
        return datetime.min
    
    def _log_resolution(
        self,
        conflict: ConflictInfo,
        winner: Dict[str, Any],
        changes: List[str]
    ):
        """
        Записать информацию о разрешении конфликта.
        
        Args:
            conflict: Информация о конфликте
            winner: Выбранная версия
            changes: Список сделанных изменений
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'entity_type': conflict.entity_type,
            'entity_id': conflict.entity_id,
            'strategy': self.strategy.value,
            'local_state': conflict.local_record,
            'remote_state': conflict.remote_record,
            'resolution': winner,
            'changes': changes,
            'local_timestamp': conflict.local_timestamp.isoformat(),
            'remote_timestamp': conflict.remote_timestamp.isoformat()
        }
        
        self.conflict_log.append(log_entry)
        
        logger.debug(f"Conflict resolved: {len(changes)} changes made")
    
    def get_conflict_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику разрешенных конфликтов.
        
        Returns:
            Словарь со статистикой
        """
        if not self.conflict_log:
            return {
                'total_conflicts': 0,
                'by_entity_type': {},
                'by_strategy': {},
                'average_changes': 0
            }
        
        stats = {
            'total_conflicts': len(self.conflict_log),
            'by_entity_type': {},
            'by_strategy': {},
            'average_changes': 0
        }
        
        total_changes = 0
        
        for entry in self.conflict_log:
            entity_type = entry['entity_type']
            strategy = entry['strategy']
            changes_count = len(entry['changes'])
            
            # По типу сущности
            if entity_type not in stats['by_entity_type']:
                stats['by_entity_type'][entity_type] = 0
            stats['by_entity_type'][entity_type] += 1
            
            # По стратегии
            if strategy not in stats['by_strategy']:
                stats['by_strategy'][strategy] = 0
            stats['by_strategy'][strategy] += 1
            
            total_changes += changes_count
        
        stats['average_changes'] = total_changes / len(self.conflict_log)
        
        return stats
    
    def export_conflict_log(self, filepath: str) -> bool:
        """
        Экспортировать лог конфликтов в JSON файл.
        
        Args:
            filepath: Путь к файлу
            
        Returns:
            True если успешно
        """
        try:
            import json
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conflict_log, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Conflict log exported: {len(self.conflict_log)} entries")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export conflict log: {e}")
            return False


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_conflict_info_from_records(
    local: Dict[str, Any],
    remote: Dict[str, Any],
    entity_type: str,
    entity_id: str
) -> ConflictInfo:
    """
    Создать ConflictInfo из двух записей.
    
    Автоматически извлекает timestamp'ы из записей.
    
    Args:
        local: Локальная запись
        remote: Удаленная запись
        entity_type: Тип сущности
        entity_id: ID сущности
        
    Returns:
        ConflictInfo объект
    """
    # Извлечь timestamp'ы
    local_ts = _extract_timestamp(local)
    remote_ts = _extract_timestamp(remote)
    
    return ConflictInfo(
        local_record=local,
        remote_record=remote,
        local_timestamp=local_ts,
        remote_timestamp=remote_ts,
        entity_type=entity_type,
        entity_id=entity_id
    )


def _extract_timestamp(record: Dict[str, Any]) -> datetime:
    """Извлечь timestamp из записи"""
    # Попытаться найти timestamp в различных полях
    for field in ['timestamp', 'last_modified', 'updated_at', 'modified_at']:
        if field in record:
            value = record[field]
            
            if isinstance(value, datetime):
                return value
            
            if isinstance(value, str):
                try:
                    # Убрать timezone
                    if '+' in value:
                        value = value.split('+')[0]
                    if 'Z' in value:
                        value = value.replace('Z', '')
                    
                    return datetime.fromisoformat(value)
                except:
                    pass
    
    # Fallback
    return datetime.min


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Пример использования ConflictResolver.
    
    Запуск:
        python sync/conflict_resolver.py
    """
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("ConflictResolver - Usage Examples")
    print("=" * 80)
    print()
    
    # Пример 1: Last Write Wins
    print("Example 1: LAST_WRITE_WINS strategy")
    
    resolver = ConflictResolver(strategy=ConflictResolutionStrategy.LAST_WRITE_WINS)
    
    conflict = ConflictInfo(
        local_record={
            'email': 'user@example.com',
            'status': 'Обед',
            'timestamp': '2025-11-24T10:00:00',
            'comment': 'Local comment'
        },
        remote_record={
            'email': 'user@example.com',
            'status': 'В работе',
            'timestamp': '2025-11-24T10:05:00',
            'comment': 'Remote comment'
        },
        local_timestamp=datetime(2025, 11, 24, 10, 0, 0),
        remote_timestamp=datetime(2025, 11, 24, 10, 5, 0),
        entity_type='STATUS_CHANGE',
        entity_id='user@example.com'
    )
    
    winner = resolver.resolve(conflict)
    print(f"Winner: {winner['status']} (timestamp: {winner['timestamp']})")
    print()
    
    # Пример 2: Merge Strategy
    print("Example 2: MERGE strategy")
    
    resolver_merge = ConflictResolver(strategy=ConflictResolutionStrategy.MERGE)
    winner_merge = resolver_merge.resolve(conflict)
    print(f"Merged result: {winner_merge}")
    print()
    
    # Пример 3: Статистика
    print("Example 3: Statistics")
    stats = resolver_merge.get_conflict_statistics()
    print(f"Total conflicts resolved: {stats['total_conflicts']}")
    print(f"By entity type: {stats['by_entity_type']}")
    print(f"Average changes per conflict: {stats['average_changes']:.2f}")
    print()
    
    print("=" * 80)
