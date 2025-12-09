"""
Улучшенная система батчинга для Google Sheets API
Объединяет множество операций в минимальное количество API запросов
"""
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("sheets_batching")


@dataclass
class BatchOperation:
    """Одна операция для батча"""
    operation_type: str  # 'append', 'update', 'read'
    sheet_name: str
    data: Any = None
    range_a1: str = None  # Для update operations
    row_number: int = None  # Для update операций по номеру строки


@dataclass
class BatchRequest:
    """Батч-запрос к Google Sheets"""
    operations: List[BatchOperation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_append(self, sheet_name: str, rows: List[List[Any]]):
        """Добавить операцию append"""
        self.operations.append(BatchOperation(
            operation_type='append',
            sheet_name=sheet_name,
            data=rows
        ))
    
    def add_update(self, sheet_name: str, range_a1: str, values: List[List[Any]]):
        """Добавить операцию update"""
        self.operations.append(BatchOperation(
            operation_type='update',
            sheet_name=sheet_name,
            range_a1=range_a1,
            data=values
        ))
    
    def add_row_update(self, sheet_name: str, row_number: int, values: List[Any]):
        """Добавить операцию обновления строки"""
        self.operations.append(BatchOperation(
            operation_type='update_row',
            sheet_name=sheet_name,
            row_number=row_number,
            data=values
        ))
    
    def size(self) -> int:
        """Количество операций в батче"""
        return len(self.operations)


class BatchManager:
    """
    Менеджер батч-операций для Google Sheets
    
    Использование:
    
    # Создаем батч
    batch = BatchManager(sheets_api)
    
    # Добавляем операции
    batch.add_append("WorkLog", [[email, name, status, ...]])
    batch.add_append("WorkLog", [[email2, name2, status2, ...]])
    batch.add_update("ActiveSessions", "A2:K2", [[email, name, ...]])
    
    # Выполняем все операции одним запросом
    batch.execute()
    """
    
    def __init__(self, sheets_api, max_batch_size: int = 50):
        """
        Args:
            sheets_api: Экземпляр SheetsAPI
            max_batch_size: Максимум операций в одном батче
        """
        self.api = sheets_api
        self.max_batch_size = max_batch_size
        self.batch = BatchRequest()
        self.auto_flush = True  # Автоматически выполнять при достижении лимита
        
    def add_append(self, sheet_name: str, rows: List[List[Any]]):
        """Добавить строки (append)"""
        self.batch.add_append(sheet_name, rows)
        if self.auto_flush and self.batch.size() >= self.max_batch_size:
            self.execute()
    
    def add_update(self, sheet_name: str, range_a1: str, values: List[List[Any]]):
        """Обновить диапазон"""
        self.batch.add_update(sheet_name, range_a1, values)
        if self.auto_flush and self.batch.size() >= self.max_batch_size:
            self.execute()
    
    def add_row_update(self, sheet_name: str, row_number: int, values: List[Any]):
        """Обновить конкретную строку"""
        self.batch.add_row_update(sheet_name, row_number, values)
        if self.auto_flush and self.batch.size() >= self.max_batch_size:
            self.execute()
    
    def execute(self) -> Tuple[int, int]:
        """
        Выполнить все накопленные операции
        
        Returns:
            (успешных_операций, неудачных_операций)
        """
        if self.batch.size() == 0:
            logger.debug("No operations to execute")
            return 0, 0
        
        logger.info(f"Executing batch with {self.batch.size()} operations")
        
        # Группируем операции по типу и листу
        grouped_ops = self._group_operations()
        
        success_count = 0
        fail_count = 0
        
        # Выполняем append операции батчами
        for sheet_name, append_ops in grouped_ops['appends'].items():
            all_rows = []
            for op in append_ops:
                all_rows.extend(op.data)
            
            try:
                logger.info(f"Batch append to '{sheet_name}': {len(all_rows)} rows")
                ws = self.api.get_worksheet(sheet_name)
                
                # Разбиваем на чанки если слишком много
                chunk_size = 200
                for i in range(0, len(all_rows), chunk_size):
                    chunk = all_rows[i:i + chunk_size]
                    ws.append_rows(chunk, value_input_option='USER_ENTERED')
                    success_count += len(chunk)
                    logger.debug(f"  Appended chunk: {len(chunk)} rows")
                
            except Exception as e:
                logger.error(f"Batch append failed for '{sheet_name}': {e}")
                fail_count += len(all_rows)
        
        # Выполняем update операции батчами
        for sheet_name, update_ops in grouped_ops['updates'].items():
            try:
                logger.info(f"Batch update to '{sheet_name}': {len(update_ops)} operations")
                ws = self.api.get_worksheet(sheet_name)
                
                # Используем batch_update API
                batch_data = []
                for op in update_ops:
                    if op.operation_type == 'update':
                        batch_data.append({
                            'range': f"{sheet_name}!{op.range_a1}",
                            'values': op.data
                        })
                    elif op.operation_type == 'update_row':
                        # Определяем диапазон для строки
                        last_col = len(op.data)
                        col_letter = self._number_to_column(last_col)
                        range_a1 = f"A{op.row_number}:{col_letter}{op.row_number}"
                        batch_data.append({
                            'range': f"{sheet_name}!{range_a1}",
                            'values': [op.data]
                        })
                
                # Выполняем batch update
                if batch_data:
                    self.api.client.open_by_key(self.api._sheet_id).batch_update(
                        batch_data,
                        value_input_option='USER_ENTERED'
                    )
                    success_count += len(batch_data)
                
            except Exception as e:
                logger.error(f"Batch update failed for '{sheet_name}': {e}")
                fail_count += len(update_ops)
        
        logger.info(f"Batch execution complete: {success_count} success, {fail_count} failed")
        
        # Очищаем батч
        self.batch = BatchRequest()
        
        return success_count, fail_count
    
    def _group_operations(self) -> Dict[str, Dict[str, List[BatchOperation]]]:
        """Группирует операции по типу и листу"""
        grouped = {
            'appends': {},
            'updates': {},
        }
        
        for op in self.batch.operations:
            if op.operation_type == 'append':
                if op.sheet_name not in grouped['appends']:
                    grouped['appends'][op.sheet_name] = []
                grouped['appends'][op.sheet_name].append(op)
            else:  # update или update_row
                if op.sheet_name not in grouped['updates']:
                    grouped['updates'][op.sheet_name] = []
                grouped['updates'][op.sheet_name].append(op)
        
        return grouped
    
    def _number_to_column(self, n: int) -> str:
        """Конвертирует номер колонки в букву (1->A, 26->Z, 27->AA)"""
        result = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = chr(65 + remainder) + result
        return result
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматически выполнить при выходе из контекста"""
        if self.batch.size() > 0:
            self.execute()
        return False


# Пример использования:
"""
from sheets_batching import BatchManager

# Вместо 200 отдельных запросов:
for user in users:
    api.append_row("WorkLog", [user.email, user.name, ...])  # 200 запросов!

# Используйте батчинг:
with BatchManager(api) as batch:
    for user in users:
        batch.add_append("WorkLog", [[user.email, user.name, ...]])
# При выходе из with - автоматически выполнится один батч-запрос!

# Или вручную:
batch = BatchManager(api)
for user in users:
    batch.add_append("WorkLog", [[user.email, user.name, ...]])
batch.execute()  # Один запрос вместо 200!
"""
