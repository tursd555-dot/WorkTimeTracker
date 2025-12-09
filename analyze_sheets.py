"""
Скрипт для анализа Google Sheets таблицы WorkLog
Показывает полную информацию обо всех листах, их содержимом и использовании
"""

import sys
import logging
from datetime import datetime, timedelta
from collections import defaultdict

# Добавляем путь к модулям
sys.path.insert(0, 'D:\\proj vs code\\WorkTimeTracker')

from api_adapter import SheetsAPI

# Настройка логгера
logger = logging.getLogger(__name__)

def format_size(num):
    """Форматирование размера в человекочитаемый вид."""
    for unit in ['', 'K', 'M']:
        if abs(num) < 1000.0:
            return f"{num:.0f}{unit}"
        num /= 1000.0
    return f"{num:.0f}G"

def analyze_worksheet(api, ws_title):
    """Детальный анализ одного листа."""
    try:
        ws = api.get_worksheet(ws_title)
        
        # Получаем все данные
        all_data = ws.get_all_values()
        
        if not all_data:
            return {
                'title': ws_title,
                'rows': 0,
                'cols': 0,
                'cells': 0,
                'empty': True,
                'has_header': False,
                'header': [],
                'sample_data': [],
                'date_range': None,
                'users': set(),
                'status_types': set(),
                'action_types': set(),
            }
        
        # Основная информация
        rows = len(all_data)
        cols = len(all_data[0]) if rows > 0 else 0
        cells = rows * cols
        
        # Заголовок (первая строка)
        header = all_data[0] if rows > 0 else []
        has_header = bool(header and any(h.strip() for h in header))
        
        # Проверка на пустоту (без заголовка)
        data_rows = all_data[1:] if has_header else all_data
        empty = not any(any(cell.strip() for cell in row) for row in data_rows)
        
        # Примеры данных (первые 3 строки после заголовка)
        sample_data = []
        for row in data_rows[:3]:
            if any(cell.strip() for cell in row):
                sample_data.append(row)
        
        # Анализ данных по колонкам
        date_range = None
        users = set()
        status_types = set()
        action_types = set()
        
        # Ищем колонки с данными
        timestamp_col = None
        email_col = None
        status_col = None
        action_col = None
        
        for idx, h in enumerate(header):
            h_lower = h.lower().strip()
            if h_lower in ['timestamp', 'дата', 'время', 'datetime']:
                timestamp_col = idx
            elif h_lower in ['email', 'емайл', 'почта']:
                email_col = idx
            elif h_lower in ['status', 'статус']:
                status_col = idx
            elif h_lower in ['actiontype', 'action', 'действие', 'тип']:
                action_col = idx
        
        # Собираем статистику
        dates = []
        for row in data_rows:
            if not any(cell.strip() for cell in row):
                continue
                
            # Email
            if email_col is not None and email_col < len(row):
                email = row[email_col].strip()
                if email and '@' in email:
                    users.add(email)
            
            # Status
            if status_col is not None and status_col < len(row):
                status = row[status_col].strip()
                if status:
                    status_types.add(status)
            
            # Action
            if action_col is not None and action_col < len(row):
                action = row[action_col].strip()
                if action:
                    action_types.add(action)
            
            # Timestamp
            if timestamp_col is not None and timestamp_col < len(row):
                ts = row[timestamp_col].strip()
                if ts:
                    try:
                        # Пробуем разные форматы
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                            try:
                                dt = datetime.strptime(ts.split('.')[0][:19], fmt)
                                dates.append(dt)
                                break
                            except:
                                continue
                    except:
                        pass
        
        # Диапазон дат
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            date_range = {
                'min': min_date.strftime('%Y-%m-%d'),
                'max': max_date.strftime('%Y-%m-%d'),
                'days': (max_date - min_date).days
            }
        
        return {
            'title': ws_title,
            'rows': rows,
            'cols': cols,
            'cells': cells,
            'empty': empty,
            'has_header': has_header,
            'header': header,
            'sample_data': sample_data,
            'date_range': date_range,
            'users': users,
            'status_types': status_types,
            'action_types': action_types,
            'data_rows': len(data_rows),
        }
        
    except Exception as e:
        return {
            'title': ws_title,
            'error': str(e),
            'rows': 0,
            'cols': 0,
            'cells': 0,
        }

def main():
    print("="*100)
    print("📊 АНАЛИЗ GOOGLE SHEETS ТАБЛИЦЫ WorkLog")
    print("="*100)
    print()
    
    # Инициализация API
    print("🔄 Подключение к Google Sheets...")
    api = SheetsAPI()
    
    # Получаем название таблицы через client
    try:
        spreadsheet = api.client.open_by_key(api._sheet_id)
        print(f"✅ Подключено к таблице: {spreadsheet.title}")
    except Exception as e:
        print(f"⚠️  Подключено к таблице (название недоступно): {api._sheet_id}")
        logger.warning(f"Could not get spreadsheet title: {e}")
    print()
    
    # Получаем список всех листов
    worksheets = api.list_worksheet_titles()
    print(f"📋 Всего листов: {len(worksheets)}")
    print()
    
    # Категории листов
    categories = {
        'WorkLog': [],      # Листы с логами работы
        'Config': [],       # Конфигурационные листы
        'Break': [],        # Листы перерывов
        'Other': [],        # Остальные
    }
    
    # Анализируем каждый лист
    results = []
    total_cells = 0
    total_data_rows = 0
    
    print("🔍 Анализ листов...")
    print("-"*100)
    
    for ws in worksheets:
        print(f"   Анализ: {ws.title}...", end='', flush=True)
        result = analyze_worksheet(api, ws.title)
        results.append(result)
        
        if 'error' not in result:
            total_cells += result['cells']
            total_data_rows += result.get('data_rows', 0)
            print(f" ✅ ({result['rows']} строк)")
            
            # Категоризация
            title_lower = ws.title.lower()
            if 'worklog' in title_lower:
                categories['WorkLog'].append(result)
            elif 'break' in title_lower or 'перерыв' in title_lower:
                categories['Break'].append(result)
            elif ws.title in ['Users', 'Groups', 'Admins', 'ActiveSessions', 'AccessControl', 
                             'NotificationsLog', 'NotificationRules']:
                categories['Config'].append(result)
            else:
                categories['Other'].append(result)
        else:
            print(f" ❌ Ошибка: {result['error']}")
    
    print("-"*100)
    print()
    
    # Общая статистика
    print("="*100)
    print("📈 ОБЩАЯ СТАТИСТИКА")
    print("="*100)
    print(f"Всего листов: {len(worksheets)}")
    print(f"Всего ячеек: {format_size(total_cells)}")
    print(f"Строк данных: {format_size(total_data_rows)}")
    print()
    
    # Статистика по категориям
    print("="*100)
    print("📂 КАТЕГОРИИ ЛИСТОВ")
    print("="*100)
    print()
    
    for category, sheets in categories.items():
        if not sheets:
            continue
            
        print(f"{'─'*100}")
        print(f"📁 {category} ({len(sheets)} листов)")
        print(f"{'─'*100}")
        
        for sheet in sheets:
            if 'error' in sheet:
                print(f"   ❌ {sheet['title']}: ОШИБКА - {sheet['error']}")
                continue
            
            # Основная информация
            status = "🟢 АКТИВНЫЙ" if not sheet['empty'] else "⚪ ПУСТОЙ"
            print(f"   {status} {sheet['title']}")
            print(f"      ├─ Размер: {sheet['rows']} строк × {sheet['cols']} колонок = {format_size(sheet['cells'])} ячеек")
            print(f"      ├─ Данных: {sheet.get('data_rows', 0)} строк")
            
            # Заголовок
            if sheet['has_header'] and sheet['header']:
                header_str = ', '.join([h for h in sheet['header'][:5] if h.strip()])
                if len(sheet['header']) > 5:
                    header_str += f" ... (+{len(sheet['header']) - 5} колонок)"
                print(f"      ├─ Колонки: {header_str}")
            
            # Диапазон дат
            if sheet['date_range']:
                dr = sheet['date_range']
                print(f"      ├─ Период: {dr['min']} → {dr['max']} ({dr['days']} дней)")
            
            # Пользователи
            if sheet['users']:
                users_str = ', '.join(list(sheet['users'])[:3])
                if len(sheet['users']) > 3:
                    users_str += f" ... (+{len(sheet['users']) - 3} пользователей)"
                print(f"      ├─ Пользователи ({len(sheet['users'])}): {users_str}")
            
            # Статусы
            if sheet['status_types']:
                status_str = ', '.join(list(sheet['status_types'])[:5])
                if len(sheet['status_types']) > 5:
                    status_str += f" ... (+{len(sheet['status_types']) - 5})"
                print(f"      ├─ Статусы ({len(sheet['status_types'])}): {status_str}")
            
            # Типы действий
            if sheet['action_types']:
                action_str = ', '.join(list(sheet['action_types'])[:5])
                if len(sheet['action_types']) > 5:
                    action_str += f" ... (+{len(sheet['action_types']) - 5})"
                print(f"      ├─ Действия ({len(sheet['action_types'])}): {action_str}")
            
            # Примеры данных
            if sheet['sample_data'] and not sheet['empty']:
                print(f"      └─ Примеры данных:")
                for idx, row in enumerate(sheet['sample_data'][:2], 1):
                    row_str = ' | '.join([cell[:20] for cell in row[:4] if cell.strip()])
                    print(f"         {idx}. {row_str}")
            
            print()
        
        print()
    
    # Рекомендации по очистке
    print("="*100)
    print("🧹 РЕКОМЕНДАЦИИ ПО ОЧИСТКЕ")
    print("="*100)
    print()
    
    # Пустые листы
    empty_sheets = [r for r in results if r.get('empty', False) and 'error' not in r]
    if empty_sheets:
        print(f"⚪ ПУСТЫЕ ЛИСТЫ ({len(empty_sheets)}) - можно удалить:")
        for sheet in empty_sheets:
            print(f"   • {sheet['title']}")
        print()
    
    # Старые данные
    old_sheets = []
    cutoff_date = datetime.now() - timedelta(days=90)  # 3 месяца
    for r in results:
        if 'error' not in r and r.get('date_range'):
            max_date = datetime.strptime(r['date_range']['max'], '%Y-%m-%d')
            if max_date < cutoff_date:
                old_sheets.append((r, r['date_range']['max']))
    
    if old_sheets:
        print(f"🕒 СТАРЫЕ ДАННЫЕ (>90 дней) ({len(old_sheets)}) - возможно устарели:")
        for sheet, max_date in sorted(old_sheets, key=lambda x: x[1]):
            print(f"   • {sheet['title']}: последняя запись {max_date}")
        print()
    
    # Дублирующиеся листы
    worklog_sheets = [r for r in results if r['title'].startswith('WorkLog_') and not r.get('empty', False)]
    if len(worklog_sheets) > 5:
        print(f"📋 МНОГО ЛИСТОВ WORKLOG ({len(worklog_sheets)}) - возможно есть дубликаты:")
        for sheet in sorted(worklog_sheets, key=lambda x: x.get('data_rows', 0), reverse=True):
            print(f"   • {sheet['title']}: {sheet.get('data_rows', 0)} строк")
        print()
    
    # Неиспользуемые листы (нет данных за последний месяц)
    recent_cutoff = datetime.now() - timedelta(days=30)
    inactive_sheets = []
    for r in results:
        if 'error' not in r and r.get('date_range') and not r.get('empty'):
            max_date = datetime.strptime(r['date_range']['max'], '%Y-%m-%d')
            if max_date < recent_cutoff:
                inactive_sheets.append((r, r['date_range']['max']))
    
    if inactive_sheets:
        print(f"💤 НЕАКТИВНЫЕ ЛИСТЫ (>30 дней без записей) ({len(inactive_sheets)}):")
        for sheet, max_date in sorted(inactive_sheets, key=lambda x: x[1]):
            print(f"   • {sheet['title']}: последняя запись {max_date}")
        print()
    
    print("="*100)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*100)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
