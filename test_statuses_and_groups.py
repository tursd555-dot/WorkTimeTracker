#!/usr/bin/env python3
"""
Тестовый скрипт для проверки учета статусов и групп в базе данных

Проверяет:
1. Какие статусы записываются в work_log
2. Какие группы есть в системе
3. Корректность связи между пользователями и группами
4. Статистику по статусам для каждой группы (Входящие, Почта, Запись, Стоматология)
"""
import sys
import os
from datetime import datetime, date, timedelta
from collections import defaultdict

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_adapter import get_sheets_api
from admin_app.repo import AdminRepo

def test_statuses_and_groups():
    """Тестирует учет статусов и групп"""
    print("=" * 80)
    print("ТЕСТ: Проверка учета статусов и групп в базе данных")
    print("=" * 80)
    print()
    
    try:
        # Инициализация API
        print("1. Инициализация API...")
        api = get_sheets_api()
        print(f"   ✅ API тип: {type(api).__name__}")
        print()
        
        # Инициализация репозитория
        print("2. Инициализация репозитория...")
        repo = AdminRepo(api)
        print()
        
        # Проверка пользователей и групп
        print("3. Проверка пользователей и групп...")
        try:
            users = repo.list_users()
            print(f"   ✅ Всего пользователей: {len(users)}")
            
            # Извлекаем группы
            groups_set = set()
            users_by_group = defaultdict(list)
            
            for user in users:
                email = user.get("Email", "")
                name = user.get("Name", "")
                group = user.get("Group", "").strip()
                
                if group:
                    groups_set.add(group)
                    users_by_group[group].append({
                        'email': email,
                        'name': name
                    })
            
            print(f"   ✅ Уникальных групп: {len(groups_set)}")
            print(f"   📋 Группы: {sorted(groups_set)}")
            print()
            
            # Проверяем целевые группы
            target_groups = ["Входящие", "Почта", "Запись", "Стоматология"]
            print("   📋 Проверка целевых групп:")
            for group in target_groups:
                if group in groups_set:
                    users_count = len(users_by_group[group])
                    print(f"      ✅ {group}: {users_count} сотрудников")
                    for user in users_by_group[group][:5]:  # Показываем первых 5
                        print(f"         - {user['name']} ({user['email']})")
                    if users_count > 5:
                        print(f"         ... и еще {users_count - 5} сотрудников")
                else:
                    print(f"      ⚠️  {group}: группа не найдена")
            print()
            
        except Exception as e:
            print(f"   ❌ Ошибка при получении пользователей: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Проверка work_log
        print("4. Проверка таблицы work_log...")
        try:
            # Проверяем данные за последние 7 дней
            date_from = (date.today() - timedelta(days=7)).isoformat()
            date_to = date.today().isoformat()
            
            print(f"   Период: {date_from} - {date_to}")
            
            work_log_data = repo.get_work_log_data(
                date_from=date_from,
                date_to=date_to
            )
            
            print(f"   ✅ Всего записей в work_log: {len(work_log_data)}")
            
            if work_log_data:
                # Проверяем структуру первой записи
                first_entry = work_log_data[0]
                print(f"   📋 Структура записи (ключи): {list(first_entry.keys())}")
                print(f"   📋 Пример записи:")
                for key, value in list(first_entry.items())[:10]:  # Первые 10 полей
                    print(f"      {key}: {value}")
                print()
                
                # Анализируем email в work_log
                emails_in_work_log = defaultdict(int)
                emails_with_status = defaultdict(set)
                emails_without_status = []
                
                for entry in work_log_data:
                    email = entry.get('email', '').lower() or entry.get('Email', '').lower()
                    status = entry.get('status', '') or entry.get('Status', '')
                    
                    if email:
                        emails_in_work_log[email] += 1
                        if status:
                            emails_with_status[email].add(status)
                        else:
                            emails_without_status.append(email)
                
                print(f"   📋 Уникальных email в work_log: {len(emails_in_work_log)}")
                print(f"   📋 Email с записями (топ-10):")
                for email, count in sorted(emails_in_work_log.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"      {email}: {count} записей, статусы: {sorted(emails_with_status.get(email, set()))}")
                print()
                
                if emails_without_status:
                    unique_no_status = set(emails_without_status)
                    print(f"   ⚠️  Email с записями без статуса ({len(unique_no_status)}):")
                    for email in list(unique_no_status)[:10]:
                        print(f"      {email}")
                    if len(unique_no_status) > 10:
                        print(f"      ... и еще {len(unique_no_status) - 10}")
                    print()
                
                # Сравниваем email из work_log с email из групп
                users_dict = {u.get("Email", "").lower(): u for u in users}
                users_emails = set(users_dict.keys())
                work_log_emails = set(emails_in_work_log.keys())
                
                print(f"   📋 Сравнение email:")
                print(f"      Email в users: {len(users_emails)}")
                print(f"      Email в work_log: {len(work_log_emails)}")
                
                emails_only_in_work_log = work_log_emails - users_emails
                emails_only_in_users = users_emails - work_log_emails
                
                if emails_only_in_work_log:
                    print(f"      ⚠️  Email только в work_log (не найдены в users): {len(emails_only_in_work_log)}")
                    for email in list(emails_only_in_work_log)[:5]:
                        print(f"         {email}")
                    if len(emails_only_in_work_log) > 5:
                        print(f"         ... и еще {len(emails_only_in_work_log) - 5}")
                    print()
                
                if emails_only_in_users:
                    print(f"      ⚠️  Email только в users (нет записей в work_log): {len(emails_only_in_users)}")
                    for email in list(emails_only_in_users)[:10]:
                        user = users_dict.get(email, {})
                        group = user.get('Group', 'Без группы')
                        print(f"         {email} (группа: {group})")
                    if len(emails_only_in_users) > 10:
                        print(f"         ... и еще {len(emails_only_in_users) - 10}")
                    print()
                
                # Анализируем статусы
                statuses = defaultdict(int)
                statuses_by_group = defaultdict(lambda: defaultdict(int))
                
                for entry in work_log_data:
                    status = entry.get('status', '') or entry.get('Status', '')
                    email = entry.get('email', '').lower() or entry.get('Email', '').lower()
                    
                    if status:
                        statuses[status] += 1
                        
                        # Определяем группу пользователя
                        user = users_dict.get(email, {})
                        group = user.get('Group', 'Без группы')
                        statuses_by_group[group][status] += 1
                
                print(f"   ✅ Уникальных статусов: {len(statuses)}")
                print(f"   📋 Статусы (общее количество записей):")
                for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
                    print(f"      {status}: {count} записей")
                print()
                
                # Проверяем статусы для целевых групп
                print("   📋 Статусы по целевым группам:")
                for group in target_groups:
                    if group in statuses_by_group:
                        group_statuses = statuses_by_group[group]
                        total = sum(group_statuses.values())
                        print(f"      {group} (всего записей: {total}):")
                        for status, count in sorted(group_statuses.items(), key=lambda x: x[1], reverse=True):
                            percent = (count / total * 100) if total > 0 else 0
                            print(f"         {status}: {count} ({percent:.1f}%)")
                    else:
                        print(f"      ⚠️  {group}: нет записей в work_log")
                print()
                
            else:
                print(f"   ⚠️  Нет данных в work_log за указанный период")
                print()
                
        except Exception as e:
            print(f"   ❌ Ошибка при получении данных из work_log: {e}")
            import traceback
            traceback.print_exc()
            print()
        
        # Детальная проверка для каждой целевой группы
        print("5. Детальная проверка для каждой целевой группы...")
        for group in target_groups:
            print(f"\n   📊 Группа: {group}")
            print("   " + "-" * 70)
            
            try:
                # Получаем пользователей группы
                group_users = users_by_group.get(group, [])
                if not group_users:
                    print(f"      ⚠️  Нет пользователей в группе {group}")
                    continue
                
                print(f"      Сотрудников: {len(group_users)}")
                
                # Получаем данные work_log для группы
                group_work_log = repo.get_work_log_data(
                    date_from=date_from,
                    date_to=date_to,
                    group=group
                )
                
                print(f"      Записей в work_log: {len(group_work_log)}")
                
                if group_work_log:
                    # Анализируем по сотрудникам
                    user_stats = defaultdict(lambda: {'statuses': defaultdict(int), 'total': 0})
                    
                    for entry in group_work_log:
                        email = entry.get('email', '').lower() or entry.get('Email', '').lower()
                        status = entry.get('status', '') or entry.get('Status', '')
                        
                        if email and status:
                            user_stats[email]['statuses'][status] += 1
                            user_stats[email]['total'] += 1
                    
                    print(f"      Сотрудников с активностью: {len(user_stats)}")
                    print(f"      Топ-5 сотрудников по активности:")
                    
                    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:5]
                    for email, stats in sorted_users:
                        user = users_dict.get(email, {})
                        name = user.get('Name', '')
                        display_name = f"{name} ({email})" if name else email
                        print(f"         {display_name}: {stats['total']} записей")
                        top_statuses = sorted(stats['statuses'].items(), key=lambda x: x[1], reverse=True)[:3]
                        for status, count in top_statuses:
                            print(f"            - {status}: {count}")
                
                # Проверяем наличие всех важных статусов
                important_statuses = ["В работе", "На задаче", "Перерыв", "Обед", "Отсутствует"]
                found_statuses = set()
                
                for entry in group_work_log:
                    status = entry.get('status', '') or entry.get('Status', '')
                    if status:
                        found_statuses.add(status)
                
                print(f"      Статусы в группе: {sorted(found_statuses)}")
                
                missing_statuses = set(important_statuses) - found_statuses
                if missing_statuses:
                    print(f"      ⚠️  Отсутствующие важные статусы: {missing_statuses}")
                else:
                    print(f"      ✅ Все важные статусы присутствуют")
                
                # Проверяем email сотрудников группы и их наличие в work_log
                print(f"      Проверка email сотрудников группы:")
                group_emails = {u['email'].lower() for u in group_users}
                work_log_emails = {entry.get('email', '').lower() or entry.get('Email', '').lower() 
                                  for entry in group_work_log if entry.get('email') or entry.get('Email')}
                
                emails_without_data = group_emails - work_log_emails
                if emails_without_data:
                    print(f"         ⚠️  Сотрудники без записей в work_log:")
                    for email in emails_without_data:
                        user = next((u for u in group_users if u['email'].lower() == email), None)
                        name = user['name'] if user else ''
                        print(f"            {name} ({email})")
                else:
                    print(f"         ✅ У всех сотрудников группы есть записи в work_log")
                
            except Exception as e:
                print(f"      ❌ Ошибка при проверке группы {group}: {e}")
                import traceback
                traceback.print_exc()
        
        print()
        
        # Проверка структуры таблицы work_log в Supabase
        print("6. Проверка структуры таблицы work_log...")
        try:
            if hasattr(api, 'client') and hasattr(api.client, 'table'):
                # Пробуем получить информацию о структуре таблицы
                response = api.client.table('work_log').select('*').limit(1).execute()
                
                if response.data:
                    sample = response.data[0]
                    print(f"   ✅ Таблица work_log доступна")
                    print(f"   📋 Поля таблицы: {list(sample.keys())}")
                    
                    # Проверяем наличие важных полей
                    important_fields = ['email', 'status', 'timestamp', 'session_id', 'action_type']
                    found_fields = set(sample.keys())
                    
                    for field in important_fields:
                        if field in found_fields or field.capitalize() in found_fields:
                            print(f"      ✅ Поле '{field}' присутствует")
                        else:
                            print(f"      ⚠️  Поле '{field}' отсутствует")
                else:
                    print(f"   ⚠️  Таблица work_log пуста")
            else:
                print(f"   ⚠️  Не Supabase API, проверка структуры недоступна")
        except Exception as e:
            print(f"   ❌ Ошибка при проверке структуры: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Итоговая сводка
        print("=" * 80)
        print("ИТОГОВАЯ СВОДКА")
        print("=" * 80)
        
        # Проверяем корректность данных
        issues = []
        
        # Проверка 1: Все ли целевые группы присутствуют?
        missing_groups = [g for g in target_groups if g not in groups_set]
        if missing_groups:
            issues.append(f"Отсутствующие группы: {missing_groups}")
        
        # Проверка 2: Есть ли данные для целевых групп?
        if work_log_data:
            groups_with_data = set(statuses_by_group.keys())
            groups_without_data = [g for g in target_groups if g not in groups_with_data]
            if groups_without_data:
                issues.append(f"Группы без данных в work_log: {groups_without_data}")
        
        # Проверка 3: Есть ли статусы в данных?
        if not statuses:
            issues.append("Нет статусов в данных work_log")
        
        if issues:
            print("   ⚠️  Обнаружены проблемы:")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print("   ✅ Все проверки пройдены успешно!")
        
        print()
        print("=" * 80)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_statuses_and_groups()
    sys.exit(0 if success else 1)
