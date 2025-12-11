
import sys
import logging
import time
import signal
from datetime import datetime
from threading import Event, RLock, Thread, Lock
from pathlib import Path
from typing import Dict, List, Optional
import socket
from time import monotonic

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    logging.warning("PyQt5 не найден. Сигналы GUI не будут работать. Запуск в режиме CLI.")
    class QObject: pass
    class pyqtSignal:
        def __init__(self): pass
        def emit(self, *args, **kwargs): pass

try:
    from config import (
        SYNC_INTERVAL,
        API_MAX_RETRIES,
        SYNC_BATCH_SIZE,
        SYNC_RETRY_STRATEGY,
        SYNC_INTERVAL_ONLINE,
        SYNC_INTERVAL_OFFLINE_RECOVERY
    )
    from user_app.db_local import get_db
    from api_adapter import get_sheets_api
    # сохраняем прежнее имя переменной для кода ниже
    sheets_api = get_sheets_api()
    from sync.network import is_internet_available, is_internet_available_fast
except ImportError as e:
    logging.error(f"Ошибка импорта модулей: {e}")
    raise

# Пулинг персональных правил перенесён в notifications.engine; безопасный импорт с фолбэком
try:
    from notifications.engine import poll_long_running_remote
except Exception:
    def poll_long_running_remote():
        return

# Персональные правила теперь обрабатываются через движок уведомлений, прямой импорт не нужен.

logger = logging.getLogger(__name__)

PING_PORT = 43333
PING_TIMEOUT = 3600  # 1 час

class SyncSignals(QObject):
    force_logout = pyqtSignal()
    sync_status_updated = pyqtSignal(dict)

class SyncManager(QObject):
    def __init__(self, signals: Optional[SyncSignals] = None, background_mode: bool = True):
        super().__init__()
        logger.info(f"Инициализация SyncManager: background_mode={background_mode}")
        
        # ИСПРАВЛЕНИЕ: Не создаём новое подключение к БД
        # Используем глобальное через get_db()
        from user_app.db_local import get_db
        self._db = get_db()  # Использует глобальное соединение
        
        self._db_lock = RLock()
        self._stop_event = Event()
        self.signals = signals
        self._background_mode = background_mode
        self._sync_interval = SYNC_INTERVAL if background_mode else 0
        self._last_sync_time = None
        self._is_offline_recovery = False  # Флаг для режима восстановления
        self._was_offline = False  # Флаг для отслеживания перехода offline -> online
        self._stats = {
            'total_synced': 0,
            'last_sync': None,
            'last_duration': 0,
            'success_rate': 1.0,
            'queue_size': 0
        }
        self._last_ping = time.time()
        self._last_loop_started = monotonic()
        self._tick_lock = Lock()  # Защита от перекрытия циклов синхронизации
        if background_mode:
            self._ping_thread = Thread(target=self._ping_listener, daemon=True)
            self._ping_thread.start()
            logger.debug("Ping listener поток запущен")
    
    def start(self):
        """
        Запуск фонового сервиса синхронизации в отдельном потоке.
        Используется из main.py для запуска фоновой синхронизации.
        """
        if not self._background_mode:
            logger.warning("SyncManager не в режиме background, start() игнорируется")
            return
        
        logger.info("Запуск фонового сервиса синхронизации...")
        self._service_thread = Thread(target=self.run_service, daemon=True, name="SyncService")
        self._service_thread.start()
        logger.info("✅ Фоновый сервис синхронизации запущен в отдельном потоке")

    def _check_remote_commands(self):
        logger.info("=== ПРОВЕРКА КОМАНД ===")
        # БЫСТРАЯ проверка интернета
        if not is_internet_available_fast(timeout=0.5):
            logger.debug("Проверка удаленных команд невозможна: нет интернета.")
            return

        with self._db_lock:
            email = self._db.get_current_user_email()
            logger.info(f"📧 Текущий email пользователя: {email}")
            session = self._db.get_active_session(email) if email else None
            session_id = session["session_id"] if session else None
            logger.info(f"🔑 Активная сессия: session_id={session_id}")

        if not email or not session_id:
            logger.warning("❌ Нет активной сессии для проверки удаленных команд.")
            return

        try:
            logger.info(f"🔍 Проверка статуса сессии для пользователя {email}, session_id: {session_id}")
            remote_status = self._check_user_session_status(email, session_id)
            logger.info(f"📊 Получен удаленный статус: {remote_status}")
            
            if remote_status == "kicked":
                logger.info(f"[ADMIN_LOGOUT] Обнаружен статус 'kicked' для пользователя {email}. Испускаем force_logout.")
                if self.signals:
                    self.signals.force_logout.emit()
                # Отправляем ACK подтверждение команды
                try:
                    sheets_api.ack_remote_command(email=email, session_id=session_id)
                    logger.info(f"ACK отправлен для команды kick пользователя {email}")
                except Exception as ack_error:
                    logger.error(f"Ошибка отправки ACK: {ack_error}")
                
                # Даём GUI время на отображение сообщения
                time.sleep(1)
                return
            elif remote_status == "finished":
                logger.warning(f"Получена команда 'finished' для пользователя {email}. Отправка сигнала в GUI.")
                if self.signals:
                    logger.info("Emit force_logout signal to GUI")
                    self.signals.force_logout.emit()
                # Отправляем ACK подтверждение команды
                try:
                    sheets_api.ack_remote_command(email=email, session_id=session_id)
                    logger.info(f"ACK отправлен для команды finished пользователя {email}")
                except Exception as ack_error:
                    logger.error(f"Ошибка отправки ACK: {ack_error}")
                # НЕ вызываем self.stop() здесь!
            else:
                logger.debug(f"Статус сессии в норме: {remote_status}")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке удаленных команд для {email}: {e}", exc_info=True)

    def _check_user_session_status(self, email: str, session_id: str) -> str:
        """
        Проверяет статус указанной сессии пользователя в Google Sheets.
        Возвращает: 'active', 'kicked', 'finished', 'expired', 'unknown'
        """
        try:
            return sheets_api.check_user_session_status(email, session_id)
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса сессии: {e}")
            return "unknown"

    def _ping_listener(self):
        logger.info(f"Запуск ping listener на UDP порту {PING_PORT}")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", PING_PORT))
        s.settimeout(2)
        logger.info(f"Ping listener запущен на UDP порту {PING_PORT}")
        while not self._stop_event.is_set():
            try:
                data, addr = s.recvfrom(1024)
                logger.debug(f"Получен UDP пакет от {addr}: {data}")
                if data == b"ping":
                    self._last_ping = time.time()
                    logger.debug("Получен ping, обновлено время последнего ping")
            except socket.timeout:
                continue
            except Exception as e:
                logger.warning(f"Ошибка в ping listener: {e}", exc_info=True)
        s.close()
        logger.info("Ping listener завершен")

    def _prepare_batch(self, prioritize_fresh: bool = True) -> Optional[Dict[str, List[Dict]]]:
        """
        Подготовка пакета данных для синхронизации.
        
        Args:
            prioritize_fresh: Если True, сначала синхронизируем свежие записи (< 5 минут)
        """
        logger.info(f"📋 Подготовка пакета (prioritize_fresh={prioritize_fresh})")
        with self._db_lock:
            try:
                # Если нужны приоритетные (свежие) записи
                if prioritize_fresh:
                    # Сначала проверяем есть ли свежие записи (< 15 минут)
                    logger.info("🔍 Проверяем наличие СВЕЖИХ записей (< 15 минут)...")
                    fresh = self._db.get_fresh_unsynced_actions(age_minutes=15, limit=20)
                    
                    if fresh:
                        logger.info(f"🚨 Найдено {len(fresh)} СВЕЖИХ записей (< 15 минут) - приоритетная синхронизация!")
                        unsynced = fresh
                    else:
                        logger.info("✅ Свежих записей нет, берем старые (лимит 20)")
                        # Если свежих нет, берем старые но ОГРАНИЧЕННОЕ количество
                        unsynced = self._db.get_unsynced_actions(limit=20)
                        if unsynced:
                            logger.info(f"📦 Фоновая синхронизация {len(unsynced)} старых записей")
                else:
                    logger.info(f"📦 Обычная синхронизация (лимит {SYNC_BATCH_SIZE})")
                    # Обычная синхронизация (большими пакетами)
                    unsynced = self._db.get_unsynced_actions(SYNC_BATCH_SIZE)
                
                logger.debug(f"Найдено {len(unsynced)} несинхронизированных действий")
                
                if not unsynced:
                    logger.debug("Нет данных для подготовки пакета")
                    return None
                
                batch = {}
                for action in unsynced:
                    email = action[1]
                    if email not in batch:
                        batch[email] = []
                    batch[email].append({
                        'id': action[0],
                        'email': action[1],
                        'name': action[2],
                        'status': action[3],
                        'action_type': action[4],
                        'comment': action[5],
                        'timestamp': action[6],
                        'session_id': action[7],
                        'status_start_time': action[8],
                        'status_end_time': action[9],
                        'reason': action[10],        # NEW
                        'user_group': action[11],    # NEW
                    })
                
                logger.info(f"Подготовлен пакет для {len(batch)} пользователей, всего действий: {sum(len(actions) for actions in batch.values())}")
                return batch
                
            except Exception as e:
                logger.error(f"Ошибка подготовки пакета: {e}", exc_info=True)
                return None

    def _sync_batch(self, batch: Dict[str, List[Dict]]) -> bool:
        if not batch:
            logger.debug("Пустой пакет, пропускаем синхронизацию")
            return True
            
        start_time = time.time()
        total_actions = sum(len(actions) for actions in batch.values())
        success_count = 0
        synced_ids = []
        
        logger.info(f"Начало синхронизации пакета из {total_actions} действий для {len(batch)} пользователей")
        
        for email, actions in batch.items():
            logger.debug(f"Синхронизация для пользователя {email}: {len(actions)} действий")
            
            for attempt in range(API_MAX_RETRIES):
                try:
                    logger.debug(f"Попытка {attempt + 1}/{API_MAX_RETRIES} для пользователя {email}")
                    
                    # БЫСТРАЯ проверка интернета
                    if not is_internet_available_fast(timeout=0.5):
                        logger.warning("Интернет недоступен, пропускаем синхронизацию.")
                        return False
                    
                    # Получаем группу пользователя из листа Users
                    user = sheets_api.get_user_by_email(email)
                    user_group = user.get("group") if user else None
                    
                    # Готовим список словарей для отправки
                    actions_payload = []
                    for a in actions:
                        actions_payload.append({
                            "session_id": a['session_id'],
                            "email": a['email'],
                            "name": a['name'],
                            "status": a['status'],
                            "action_type": a['action_type'],
                            "comment": a['comment'],
                            "timestamp": a['timestamp'],
                            "status_start_time": a['status_start_time'],
                            "status_end_time": a['status_end_time'],
                            "reason": a.get('reason'),
                        })

                    # Логируем детали перед отправкой
                    logger.info(f"📤 Отправка {len(actions_payload)} действий для {email} в группу {user_group}")
                    for idx, action in enumerate(actions_payload):
                        logger.debug(f"  [{idx+1}] {action['status']} at {action['timestamp']} (id={actions[idx]['id']})")
                    
                    # Используем новую сигнатуру API с передачей user_group
                    result = sheets_api.log_user_actions(actions_payload, email, user_group=user_group)
                    logger.info(f"✅ Результат отправки для {email}: {result}")
                    
                    if result:
                        success_count += len(actions)
                        synced_ids.extend([a['id'] for a in actions])
                        logger.info(f"Успешно синхронизировано {len(actions)} действий для {email}")
                        break
                    else:
                        logger.warning(f"Не удалось синхронизировать действия для {email}, попытка {attempt + 1}")
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    logger.error(f"Ошибка синхронизации для {email} (попытка {attempt + 1}): {e}", exc_info=True)
                    
                    # Проверяем DNS ошибки - прекращаем попытки немедленно
                    if 'nameresolutionerror' in error_msg or 'getaddrinfo failed' in error_msg or 'failed to resolve' in error_msg:
                        logger.error(f"❌ DNS ОШИБКА для {email}. Прекращаем попытки синхронизации.")
                        logger.error(f"Проблема: не удается резолвить sheets.googleapis.com")
                        break  # Прекращаем бесполезные повторы при DNS проблемах
                    
                    # Проверяем Circuit Breaker
                    if hasattr(sheets_api, 'circuit_breaker') and sheets_api.circuit_breaker:
                        if not sheets_api.circuit_breaker.can_execute():
                            logger.error(f"❌ Circuit Breaker ОТКРЫТ для {email}. Прекращаем попытки синхронизации.")
                            break  # Прекращаем повторы если Circuit Breaker открыт
                
                if attempt < API_MAX_RETRIES - 1:
                    delay = SYNC_RETRY_STRATEGY[min(attempt, len(SYNC_RETRY_STRATEGY) - 1)]
                    logger.info(f"Повторная попытка через {delay} сек...")
                    time.sleep(delay)
        
        if synced_ids:
            with self._db_lock:
                try:
                    logger.debug(f"Помечаем как синхронизированные {len(synced_ids)} записей: {synced_ids}")
                    self._db.mark_actions_synced(synced_ids)
                    logger.info(f"✅ Успешно синхронизировано и отмечено {len(synced_ids)} записей.")
                except Exception as e:
                    logger.error(f"Ошибка обновления статуса записей в локальной БД: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ НЕТ СИНХРОНИЗИРОВАННЫХ ЗАПИСЕЙ! Все {total_actions} записей остались в очереди.")
        
        duration = time.time() - start_time
        logger.info(f"Синхронизация завершена за {duration:.2f} сек. Успешно: {success_count}/{total_actions}")
        
        # Логируем текущий размер очереди
        queue_size = self._db.get_unsynced_count()
        logger.info(f"📊 Размер очереди после синхронизации: {queue_size} несинхронизированных записей")
        
        self._update_stats(success_count, total_actions, duration)
        return success_count == total_actions

    def _update_stats(self, success_count: int, total_actions: int, duration: float):
        logger.debug(f"Обновление статистики: success={success_count}, total={total_actions}, duration={duration:.2f}")
        with self._db_lock:
            self._stats['total_synced'] += success_count
            self._stats['last_sync'] = datetime.now().isoformat(timespec='seconds')
            self._stats['last_duration'] = round(duration, 3)
            if total_actions > 0:
                rate = success_count / total_actions
                self._stats['success_rate'] = 0.9 * self._stats['success_rate'] + 0.1 * rate
            self._stats['queue_size'] = self._db.get_unsynced_count()
            
        logger.debug(f"Обновленная статистика: {self._stats}")
        if self.signals:
            self.signals.sync_status_updated.emit(self._stats.copy())
            logger.debug("Сигнал sync_status_updated отправлен")

    def sync_once(self, prioritize_fresh: bool = True) -> bool:
        """
        Разовая синхронизация.
        
        Args:
            prioritize_fresh: Если True, приоритизируем свежие записи
        """
        logger.info("=== ЗАПУСК РАЗОВОЙ СИНХРОНИЗАЦИИ ===")
        start = time.time()
        ok = False
        try:
            batch = self._prepare_batch(prioritize_fresh=prioritize_fresh)
            if not batch:
                logger.debug("Нет данных для синхронизации.")
                return True

            total_actions = sum(len(actions) for actions in batch.values())
            logger.info(f"Начало синхронизации пакета из {total_actions} записей.")

            # Если очередь очень большая, активируем режим восстановления
            # НО только если это не приоритетная синхронизация
            if total_actions > 100 and not self._is_offline_recovery and not prioritize_fresh:
                self._is_offline_recovery = True
                self._sync_interval = SYNC_INTERVAL_OFFLINE_RECOVERY
                logger.info(f"Обнаружено большое количество действий ({total_actions}). Активирован режим восстановления.")

            ok = self._sync_batch(batch)
            logger.info(f"Результат разовой синхронизации: {'УСПЕХ' if ok else 'НЕУДАЧА'}")
        finally:
            elapsed = time.time() - start
            self._stats['last_sync'] = datetime.now().isoformat(timespec='seconds')
            self._stats['last_duration'] = round(elapsed, 3)
            self._stats['queue_size'] = self._db.get_unsynced_count()
            if ok:
                self._stats['total_synced'] += 1
            if self.signals:
                self.signals.sync_status_updated.emit(dict(self._stats))
        return ok

    def _sync_cycle(self):
        """Один цикл синхронизации с защитой от перекрытия"""
        # Не пускаем второй тик, пока идёт текущий
        if not self._tick_lock.acquire(blocking=False):
            logger.info("⏸️ Пропуск цикла: предыдущий цикл еще выполняется")  # INFO!
            return
        
        try:
            logger.info("=== НАЧАЛО ЦИКЛА СИНХРОНИЗАЦИИ ===")  # INFO!
            
            now = time.time()
            if (now - self._last_ping) > PING_TIMEOUT:
                logger.warning("Ping не получен более часа — завершаем работу сервиса.")
                self._stop_event.set()
                return
            
            start_time = time.time()
            
            # Проверяем, есть ли интернет (БЫСТРАЯ проверка)
            internet_available = is_internet_available_fast(timeout=0.5)
            logger.info(f"Доступность интернета: {internet_available}")  # INFO!
            
            # НОВОЕ: Детекция возвращения интернета
            if internet_available and self._was_offline:
                # Интернет только что вернулся!
                logger.info("🌐 ИНТЕРНЕТ ВЕРНУЛСЯ! Активируем режим восстановления")
                queue_size = self._db.get_unsynced_count()
                logger.info(f"Несинхронизированных записей: {queue_size}")
                
                if queue_size > 0:
                    self._is_offline_recovery = True
                    self._sync_interval = 1  # НЕМЕДЛЕННАЯ синхронизация!
                    logger.info(f"⚡ НЕМЕДЛЕННАЯ синхронизация {queue_size} записей")
                else:
                    self._sync_interval = SYNC_INTERVAL_ONLINE
                
                self._was_offline = False
            
            if internet_available:
                # Если интернет есть, проверяем, в каком режиме мы находимся
                if self._is_offline_recovery:
                    # Если мы в режиме восстановления, проверяем, сколько записей осталось
                    queue_size = self._db.get_unsynced_count()
                    logger.info(f"🔄 Режим восстановления. Размер очереди: {queue_size}")  # INFO!
                    
                    if queue_size < 10:  # Если осталось меньше 10 записей, считаем, что восстановление завершено
                        self._is_offline_recovery = False
                        self._sync_interval = SYNC_INTERVAL  # Возвращаемся к нормальному интервалу
                        logger.info("✅ Режим восстановления завершен. Возвращаемся к нормальному интервалу синхронизации.")
                    else:
                        # Быстрая синхронизация в режиме восстановления
                        self._sync_interval = 2  # Каждые 2 секунды
                else:
                    # Нормальный режим
                    self._sync_interval = SYNC_INTERVAL_ONLINE
            else:
                # Нет интернета — используем минимальный интервал для быстрого обнаружения его появления
                self._was_offline = True  # НОВОЕ: Отмечаем что были offline
                self._sync_interval = 5
                logger.info("❌ Нет интернета, установлен интервал 5 сек")  # INFO!

            logger.info(f"⏰ Текущий интервал синхронизации: {self._sync_interval} сек")  # INFO!
            
            # Выполняем синхронизацию
            # ПРИОРИТЕТНАЯ синхронизация: всегда синхронизируем свежие записи первыми
            self.sync_once(prioritize_fresh=True)
            self._check_remote_commands()
            
            # Проверяем долгие статусы через Engine
            try:
                poll_long_running_remote()
            except Exception:
                logger.debug("long-status monitor skipped", exc_info=True)
            
            elapsed = time.time() - start_time
            logger.debug(f"Цикл завершен за {elapsed:.2f} сек.")
            
        except Exception as e:
            logger.critical(f"Критическая ошибка в цикле синхронизации: {e}", exc_info=True)
        finally:
            self._tick_lock.release()


    def run_service(self):
        logger.info(f"Сервис синхронизации запущен. Интервал: {self._sync_interval} сек.")
        cycle_count = 0
        
        while not self._stop_event.is_set():
            cycle_count += 1
            self._last_loop_started = monotonic()
            logger.info(f"=== ЗАПУСК ЦИКЛА #{cycle_count} ===")  # INFO вместо DEBUG!
            
            self._sync_cycle()
            
            sleep_time = max(1, self._sync_interval)
            logger.info(f"Ожидание {sleep_time:.2f} сек до следующего цикла")  # INFO вместо DEBUG!
            
            # НОВОЕ: Прерываемое ожидание - проверяем каждую секунду
            # Это позволяет быстро реагировать на изменение интервала
            elapsed = 0
            while elapsed < sleep_time and not self._stop_event.is_set():
                wait_chunk = min(1, sleep_time - elapsed)
                self._stop_event.wait(wait_chunk)
                elapsed += wait_chunk
                
                # Если интервал изменился на меньший - прерываем ожидание
                if self._sync_interval < sleep_time - elapsed:
                    logger.info(f"⚡ Интервал изменился на {self._sync_interval} сек, прерываем ожидание")
                    break

        logger.info("Сервис синхронизации завершён.")

    def stop(self):
        logger.info("Остановка SyncManager...")
        self._stop_event.set()
        try:
            self._db.close()
            logger.debug("База данных закрыта")
        except Exception as e:
            logger.error(f"Ошибка при закрытии БД: {e}", exc_info=True)
        logger.info("Сервис синхронизации остановлен.")

def configure_logging(background_mode: bool):
    log_file = 'auto_sync.log' if background_mode else None
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    # Увеличиваем уровень логирования до DEBUG для более детальной информации
    logging.basicConfig(
        level=logging.DEBUG,  # Изменено с INFO на DEBUG
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Для некоторых библиотеки устанавливаем более высокий уровень, чтобы избежать слишком много логов
    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('googleapiclient').setLevel(logging.INFO)

def handle_shutdown(signum, frame):
    logger.info("Получен сигнал завершения работы (SIGTERM/SIGINT)")
    raise SystemExit("Завершение по сигналу.")

def main(background_mode: bool = True):
    configure_logging(background_mode)
    manager = None
    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        demo_signals = SyncSignals()
        def on_force_logout():
            logger.info("--- Демонстрация: получен сигнал force_logout! Приложение должно выйти. ---")
        demo_signals.force_logout.connect(on_force_logout)

        manager = SyncManager(signals=demo_signals, background_mode=background_mode)

        if background_mode:
            logger.info("Запуск в режиме сервиса (демо)")
            manager.run_service()
        else:
            logger.info("Выполнение разовой синхронизации (демо)")
            manager.sync_once()
            manager._check_remote_commands()

    except SystemExit as e:
        logger.info(f"Завершение работы: {e}")
    except Exception as e:
        logger.critical(f"Фатальная ошибка в main: {e}", exc_info=True)
    finally:
        if manager:
            manager.stop()

if __name__ == "__main__":
    main(background_mode=True)