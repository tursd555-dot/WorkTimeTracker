# login_window_patch.py
"""
Патч для LoginWindow: добавление методов set_loading и show_error
для поддержки оптимизированной версии main.py

Добавьте эти методы в класс LoginWindow
"""

def set_loading(self, is_loading: bool, message: str = ""):
    """
    Установить состояние загрузки
    
    Args:
        is_loading: True = показать загрузку, False = скрыть
        message: Сообщение о загрузке
    """
    if is_loading:
        # Блокируем кнопку входа
        if hasattr(self, 'login_button'):
            self.login_button.setEnabled(False)
            self.login_button.setText(message or "Загрузка...")
        
        # Блокируем поля ввода
        if hasattr(self, 'email_input'):
            self.email_input.setEnabled(False)
        if hasattr(self, 'password_input'):
            self.password_input.setEnabled(False)
        
        # Показываем статус
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #0066CC;")
        elif message:
            # Создаем временный label если нет
            from PyQt5.QtWidgets import QLabel
            from PyQt5.QtCore import Qt
            if not hasattr(self, '_loading_label'):
                self._loading_label = QLabel()
                self._loading_label.setAlignment(Qt.AlignCenter)
                if hasattr(self, 'layout'):
                    self.layout().addWidget(self._loading_label)
            self._loading_label.setText(message)
            self._loading_label.setStyleSheet("color: #0066CC; font-size: 10pt;")
            self._loading_label.show()
    
    else:
        # Разблокируем элементы
        if hasattr(self, 'login_button'):
            self.login_button.setEnabled(True)
            self.login_button.setText("Войти")
        
        if hasattr(self, 'email_input'):
            self.email_input.setEnabled(True)
        if hasattr(self, 'password_input'):
            self.password_input.setEnabled(True)
        
        # Скрываем статус
        if hasattr(self, 'status_label'):
            self.status_label.setText("")
        if hasattr(self, '_loading_label'):
            self._loading_label.hide()


def show_error(self, title: str, message: str):
    """
    Показать ошибку пользователю
    
    Args:
        title: Заголовок ошибки
        message: Текст ошибки
    """
    from PyQt5.QtWidgets import QMessageBox
    QMessageBox.warning(self, title, message)


# ============================================================================
# КАК ПРИМЕНИТЬ ПАТЧ
# ============================================================================

def apply_patch_to_login_window():
    """
    Применить патч к существующему классу LoginWindow
    
    Использование:
        from login_window_patch import apply_patch_to_login_window
        apply_patch_to_login_window()
    """
    from user_app.login_window import LoginWindow
    
    # Добавляем методы к классу
    LoginWindow.set_loading = set_loading
    LoginWindow.show_error = show_error
    
    print("✓ LoginWindow patched successfully")


# ============================================================================
# АЛЬТЕРНАТИВА: Полный код для добавления в login_window.py
# ============================================================================

METHODS_TO_ADD = '''
    def set_loading(self, is_loading: bool, message: str = ""):
        """
        Установить состояние загрузки
        
        Args:
            is_loading: True = показать загрузку, False = скрыть
            message: Сообщение о загрузке
        """
        if is_loading:
            # Блокируем кнопку входа
            if hasattr(self, 'login_button'):
                self.login_button.setEnabled(False)
                self.login_button.setText(message or "Загрузка...")
            
            # Блокируем поля ввода
            if hasattr(self, 'email_input'):
                self.email_input.setEnabled(False)
            if hasattr(self, 'password_input'):
                self.password_input.setEnabled(False)
            
            # Показываем статус
            if hasattr(self, 'status_label'):
                self.status_label.setText(message)
                self.status_label.setStyleSheet("color: #0066CC;")
            elif message:
                # Создаем временный label если нет
                from PyQt5.QtWidgets import QLabel
                from PyQt5.QtCore import Qt
                if not hasattr(self, '_loading_label'):
                    self._loading_label = QLabel()
                    self._loading_label.setAlignment(Qt.AlignCenter)
                    self.layout().addWidget(self._loading_label)
                self._loading_label.setText(message)
                self._loading_label.setStyleSheet("color: #0066CC; font-size: 10pt;")
                self._loading_label.show()
        
        else:
            # Разблокируем элементы
            if hasattr(self, 'login_button'):
                self.login_button.setEnabled(True)
                self.login_button.setText("Войти")
            
            if hasattr(self, 'email_input'):
                self.email_input.setEnabled(True)
            if hasattr(self, 'password_input'):
                self.password_input.setEnabled(True)
            
            # Скрываем статус
            if hasattr(self, 'status_label'):
                self.status_label.setText("")
            if hasattr(self, '_loading_label'):
                self._loading_label.hide()
    
    def show_error(self, title: str, message: str):
        """
        Показать ошибку пользователю
        
        Args:
            title: Заголовок ошибки
            message: Текст ошибки
        """
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, title, message)
'''

print("""
=============================================================================
ИНСТРУКЦИЯ ПО ПРИМЕНЕНИЮ ПАТЧА
=============================================================================

ВАРИАНТ 1: Monkey patching (быстро, без изменения файлов)
---------------------------------------------------------
В main_optimized.py добавьте в начало:

    from login_window_patch import apply_patch_to_login_window
    apply_patch_to_login_window()

ВАРИАНТ 2: Добавить методы в login_window.py (рекомендуется)
------------------------------------------------------------
Откройте user_app/login_window.py и добавьте эти методы в класс LoginWindow:

""")
print(METHODS_TO_ADD)
print("""
=============================================================================
""")
