# shared/break_status_integration.py
"""
Интеграция системы перерывов со статусами пользователя v2.1

Автоматически вызывает break_manager когда пользователь меняет статус.
Поддерживает синхронизацию активных перерывов с БД.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Специальные статусы для перерывов
BREAK_STATUS = "Перерыв"
LUNCH_STATUS = "Обед"


class BreakStatusIntegration:
    """
    Интеграция перерывов со статусами v2.1

    Изменения:
    - Синхронизация active_breaks с БД при инициализации
    - Автоматическое восстановление состояния после перезапуска
    - Поддержка как Supabase, так и Google Sheets
    """

    def __init__(self, break_manager, api=None):
        """
        Args:
            break_manager: BreakManager или BreakManagerSupabase
            api: SupabaseAPI или SheetsAPI (опционально, для синхронизации)
        """
        self.break_mgr = break_manager
        self.api = api
        self.active_breaks = {}  # email -> {break_type, start_time}

        # Пробуем получить API если не передан
        if self.api is None:
            try:
                from api_adapter import get_sheets_api
                self.api = get_sheets_api()
            except:
                pass

        # Синхронизируем активные перерывы с БД
        self._sync_active_breaks_from_db()

        logger.info("Break-Status integration v2.1 initialized")

    def _sync_active_breaks_from_db(self):
        """Синхронизирует активные перерывы из БД в память"""
        try:
            if self.api is None:
                return

            # Проверяем тип API
            api_class_name = type(self.api).__name__

            if 'Supabase' in api_class_name:
                # Для Supabase используем специальный метод
                active = self.api.get_all_active_breaks_today()
                for row in active:
                    email = row.get('email', '').lower()
                    if email:
                        self.active_breaks[email] = {
                            'break_type': row.get('break_type', 'Перерыв'),
                            'start_time': datetime.fromisoformat(
                                row['start_time'].replace('Z', '+00:00')
                            ) if row.get('start_time') else datetime.now(),
                            'id': row.get('id')
                        }
                logger.info(f"Synced {len(self.active_breaks)} active breaks from Supabase")
            else:
                # Для Google Sheets используем метод break_manager
                if hasattr(self.break_mgr, 'get_all_active_breaks'):
                    active = self.break_mgr.get_all_active_breaks()
                    for row in active:
                        email = row.get('Email', '').lower()
                        if email:
                            self.active_breaks[email] = {
                                'break_type': row.get('BreakType', 'Перерыв'),
                                'start_time': datetime.now()  # Приблизительно
                            }
                    logger.info(f"Synced {len(self.active_breaks)} active breaks from Sheets")

        except Exception as e:
            logger.warning(f"Failed to sync active breaks from DB: {e}")

    def is_break_status(self, status: str) -> bool:
        """Проверяет, является ли статус перерывом"""
        return status in [BREAK_STATUS, LUNCH_STATUS]

    def on_status_change(
        self,
        email: str,
        old_status: str,
        new_status: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Обрабатывает смену статуса

        Вызывается при каждой смене статуса пользователя
        """
        try:
            email_lower = email.lower()

            # Переход НА перерыв
            if self.is_break_status(new_status) and not self.is_break_status(old_status):
                return self._start_break(email_lower, new_status, session_id)

            # Переход С перерыва
            elif self.is_break_status(old_status) and not self.is_break_status(new_status):
                return self._end_break(email_lower, old_status)

            # Смена типа перерыва (Перерыв -> Обед или наоборот)
            elif self.is_break_status(old_status) and self.is_break_status(new_status):
                # Завершаем старый перерыв
                self._end_break(email_lower, old_status)
                # Начинаем новый
                return self._start_break(email_lower, new_status, session_id)

            return True

        except Exception as e:
            logger.error(f"Error in status change handler: {e}", exc_info=True)
            return False

    def _start_break(self, email: str, status: str, session_id: Optional[str]) -> bool:
        """Начинает перерыв через BreakManager"""
        break_type = status  # "Перерыв" или "Обед"

        logger.info(f"Starting break for {email}: {break_type}")

        success, error = self.break_mgr.start_break(
            email=email,
            break_type=break_type,
            session_id=session_id
        )

        if not success:
            logger.warning(f"Failed to start break for {email}: {error}")
            # Продолжаем даже при ошибке - не блокируем пользователя
            # return False

        # Сохраняем информацию об активном перерыве
        self.active_breaks[email.lower()] = {
            'break_type': break_type,
            'start_time': datetime.now()
        }

        logger.info(f"Break started successfully for {email}")
        return True

    def _end_break(self, email: str, status: str) -> bool:
        """Завершает перерыв через BreakManager"""
        break_type = status  # "Перерыв" или "Обед"

        logger.info(f"Ending break for {email}: {break_type}")

        success, error, duration = self.break_mgr.end_break(
            email=email,
            break_type=break_type
        )

        if not success:
            logger.warning(f"Failed to end break for {email}: {error}")
            # Продолжаем даже при ошибке
            # return False

        # Удаляем из активных
        self.active_breaks.pop(email.lower(), None)

        logger.info(f"Break ended for {email}: {duration} minutes")
        return True

    def get_active_break(self, email: str) -> Optional[dict]:
        """Получает информацию об активном перерыве"""
        return self.active_breaks.get(email.lower())

    def has_active_break(self, email: str) -> bool:
        """Проверяет, есть ли активный перерыв у пользователя"""
        return email.lower() in self.active_breaks

    def on_logout(self, email: str) -> bool:
        """
        Завершает активный перерыв при logout пользователя

        Вызывается при:
        - Принудительном logout из админки
        - Завершении смены пользователем
        - Автоматическом logout
        """
        try:
            email_lower = email.lower()

            # Проверяем есть ли активный перерыв в памяти
            if email_lower not in self.active_breaks:
                # Проверяем в БД на всякий случай
                if self.api and hasattr(self.api, 'get_active_break_for_user'):
                    try:
                        active = self.api.get_active_break_for_user(email)
                        if active:
                            break_type = active.get('break_type', 'Перерыв')
                            logger.info(f"Found orphan break in DB for {email}, ending it")
                            self.break_mgr.end_break(email, break_type)
                            return True
                    except:
                        pass

                logger.debug(f"No active break for {email} on logout")
                return True

            break_info = self.active_breaks[email_lower]
            break_type = break_info['break_type']

            logger.info(f"Auto-ending break on logout for {email}: {break_type}")

            # Завершаем перерыв
            success, error, duration = self.break_mgr.end_break(
                email=email,
                break_type=break_type
            )

            if not success:
                logger.error(f"Failed to end break on logout for {email}: {error}")

            # Принудительно удаляем из активных
            self.active_breaks.pop(email_lower, None)

            logger.info(f"Break auto-ended on logout for {email}: {duration} minutes")
            return True

        except Exception as e:
            logger.error(f"Error in logout handler for {email}: {e}", exc_info=True)
            # Принудительно удаляем из активных
            self.active_breaks.pop(email.lower(), None)
            return False

    def force_end_all_breaks(self, email: str) -> bool:
        """
        Принудительно завершает все активные перерывы пользователя

        Используется при критических ситуациях.
        """
        try:
            email_lower = email.lower()

            # Завершаем оба типа перерывов
            for break_type in [BREAK_STATUS, LUNCH_STATUS]:
                try:
                    self.break_mgr.end_break(email, break_type)
                except:
                    pass

            # Удаляем из памяти
            self.active_breaks.pop(email_lower, None)

            logger.info(f"Force-ended all breaks for {email}")
            return True

        except Exception as e:
            logger.error(f"Error force-ending breaks for {email}: {e}")
            return False


# ============================================================================
# Глобальный экземпляр (инициализируется в main)
# ============================================================================

_integration: Optional[BreakStatusIntegration] = None


def init_integration(break_manager, api=None) -> BreakStatusIntegration:
    """Инициализирует интеграцию"""
    global _integration
    _integration = BreakStatusIntegration(break_manager, api)
    logger.info("Global break integration initialized")
    return _integration


def get_integration() -> Optional[BreakStatusIntegration]:
    """Получает глобальный экземпляр"""
    return _integration


def on_status_change(
    email: str,
    old_status: str,
    new_status: str,
    session_id: Optional[str] = None
) -> bool:
    """
    Хук для обработки смены статуса

    Вызывается из user_app при каждой смене статуса
    """
    if _integration:
        return _integration.on_status_change(email, old_status, new_status, session_id)
    else:
        logger.warning("Break integration not initialized, status change ignored")
        return True


def on_logout(email: str) -> bool:
    """
    Хук для обработки logout пользователя

    Завершает активный перерыв если он есть
    Вызывается из user_app при logout/завершении смены
    """
    if _integration:
        return _integration.on_logout(email)
    else:
        logger.warning("Break integration not initialized, logout ignored")
        return True


def has_active_break(email: str) -> bool:
    """Проверяет, есть ли активный перерыв у пользователя"""
    if _integration:
        return _integration.has_active_break(email)
    return False


def get_active_break(email: str) -> Optional[dict]:
    """Получает информацию об активном перерыве"""
    if _integration:
        return _integration.get_active_break(email)
    return None


if __name__ == "__main__":
    print("Break-Status Integration v2.1")
    print("Usage: import in user_app and call on_status_change() on every status change")
    print("New features:")
    print("  - Automatic sync with DB on init")
    print("  - Support for both Supabase and Google Sheets")
    print("  - Force end all breaks method")
