#!/usr/bin/env python3
"""
WorkTimeTracker Setup Utility

CLI утилита для безопасной настройки конфигурации и credentials.

Команды:
    wtt-setup init                  - Первоначальная настройка (создание ключей)
    wtt-setup add-google <file>     - Добавить Google credentials из JSON файла
    wtt-setup add-telegram          - Добавить Telegram bot token
    wtt-setup show                  - Показать текущую конфигурацию (без секретов)
    wtt-setup rotate-key            - Ротация ключа шифрования
    wtt-setup export-ci             - Экспорт для CI/CD (GitHub Actions)
    wtt-setup verify                - Проверить конфигурацию
    wtt-setup reset                 - Сбросить всю конфигурацию (ОПАСНО!)

Установка:
    pip install click cryptography keyring

Использование:
    python tools/wtt_setup.py init
    python tools/wtt_setup.py add-google /path/to/service_account.json
    python tools/wtt_setup.py add-telegram

Или после установки пакета:
    wtt-setup init
    wtt-setup add-google /path/to/service_account.json

Автор: WorkTimeTracker Security Team
Дата: 2025-11-24
"""

import os
import sys
import json
import click
import keyring
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any

# ============================================================================
# CONSTANTS
# ============================================================================

CONFIG_DIR = Path.home() / ".wtt"
CONFIG_FILE = CONFIG_DIR / "config.enc"
KEYRING_SERVICE = "WorkTimeTracker"
KEYRING_KEY_NAME = "config_encryption_key"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_header(text: str):
    """Красивый header для вывода"""
    click.echo()
    click.echo("=" * 80)
    click.echo(f"  {text}")
    click.echo("=" * 80)
    click.echo()


def print_success(text: str):
    """Вывести сообщение об успехе"""
    click.echo(click.style(f"✅ {text}", fg='green', bold=True))


def print_error(text: str):
    """Вывести сообщение об ошибке"""
    click.echo(click.style(f"❌ {text}", fg='red', bold=True))


def print_warning(text: str):
    """Вывести предупреждение"""
    click.echo(click.style(f"⚠️  {text}", fg='yellow'))


def print_info(text: str):
    """Вывести информацию"""
    click.echo(click.style(f"ℹ️  {text}", fg='blue'))


def get_encryption_key() -> Optional[str]:
    """Получить ключ шифрования из keyring"""
    return keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)


def set_encryption_key(key: str):
    """Сохранить ключ шифрования в keyring"""
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)


def load_config() -> Dict[str, Any]:
    """Загрузить текущую конфигурацию"""
    if not CONFIG_FILE.exists():
        return {
            'google': {},
            'telegram': {},
            'sync': {
                'interval': 30,
                'batch_size': 20,
                'max_attempts': 5,
                'conflict_strategy': 'last_write_wins'
            },
            'security': {
                'db_encryption_enabled': True
            }
        }
    
    encryption_key = get_encryption_key()
    if not encryption_key:
        raise click.ClickException(
            "Encryption key not found. Run 'wtt-setup init' first."
        )
    
    cipher = Fernet(encryption_key.encode())
    
    try:
        with open(CONFIG_FILE, "rb") as f:
            encrypted_data = f.read()
        
        decrypted = cipher.decrypt(encrypted_data)
        return json.loads(decrypted)
    except Exception as e:
        raise click.ClickException(f"Failed to decrypt config: {e}")


def save_config(config: Dict[str, Any]):
    """Сохранить конфигурацию"""
    encryption_key = get_encryption_key()
    if not encryption_key:
        raise click.ClickException(
            "Encryption key not found. Run 'wtt-setup init' first."
        )
    
    cipher = Fernet(encryption_key.encode())
    
    try:
        encrypted = cipher.encrypt(json.dumps(config, indent=2).encode())
        
        with open(CONFIG_FILE, "wb") as f:
            f.write(encrypted)
        
    except Exception as e:
        raise click.ClickException(f"Failed to save config: {e}")


def validate_google_credentials(creds_json: str) -> bool:
    """Валидация Google credentials JSON"""
    try:
        creds = json.loads(creds_json)
        
        required_fields = [
            'type',
            'project_id',
            'private_key_id',
            'private_key',
            'client_email',
            'client_id'
        ]
        
        for field in required_fields:
            if field not in creds:
                print_error(f"Missing required field: {field}")
                return False
        
        if creds['type'] != 'service_account':
            print_error(f"Invalid type: {creds['type']}. Expected: service_account")
            return False
        
        return True
        
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return False


def validate_telegram_token(token: str) -> bool:
    """Базовая валидация Telegram token"""
    # Формат: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    parts = token.split(':')
    
    if len(parts) != 2:
        print_error("Invalid token format. Expected: 123456789:ABCdef...")
        return False
    
    if not parts[0].isdigit():
        print_error("Invalid token format. First part should be numeric.")
        return False
    
    if len(parts[1]) < 20:
        print_error("Invalid token format. Second part is too short.")
        return False
    
    return True


# ============================================================================
# CLI COMMANDS
# ============================================================================

@click.group()
@click.version_option(version='1.0.0', prog_name='wtt-setup')
def cli():
    """
    WorkTimeTracker Setup Utility
    
    Безопасная настройка конфигурации и credentials.
    """
    pass


@cli.command()
def init():
    """
    Первоначальная настройка.
    
    Создает:
    - Директорию конфигурации (~/.wtt)
    - Ключ шифрования (в системном keyring)
    - Пустой зашифрованный файл конфигурации
    """
    print_header("WorkTimeTracker - Первоначальная настройка")
    
    # Проверить, не инициализирован ли уже
    if CONFIG_FILE.exists() and get_encryption_key():
        print_warning("Configuration already exists!")
        if not click.confirm("Do you want to reinitialize? This will reset all settings."):
            print_info("Initialization cancelled.")
            return
    
    try:
        # Создать директорию
        CONFIG_DIR.mkdir(exist_ok=True)
        print_success(f"Created config directory: {CONFIG_DIR}")
        
        # Сгенерировать encryption key
        encryption_key = Fernet.generate_key().decode()
        
        # Сохранить в keyring
        set_encryption_key(encryption_key)
        print_success("Generated and stored encryption key in system keyring")
        
        # Создать пустой конфиг
        empty_config = {
            'google': {},
            'telegram': {},
            'sync': {
                'interval': 30,
                'batch_size': 20,
                'max_attempts': 5,
                'conflict_strategy': 'last_write_wins'
            },
            'security': {
                'db_encryption_enabled': True
            }
        }
        
        save_config(empty_config)
        print_success(f"Created encrypted config file: {CONFIG_FILE}")
        
        click.echo()
        print_success("Initialization completed successfully! 🎉")
        click.echo()
        print_info("Next steps:")
        click.echo("  1. Add Google credentials: wtt-setup add-google /path/to/service_account.json")
        click.echo("  2. Add Telegram token: wtt-setup add-telegram")
        click.echo("  3. Verify setup: wtt-setup verify")
        
    except Exception as e:
        print_error(f"Initialization failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument('credentials_file', type=click.Path(exists=True))
@click.option('--spreadsheet-id', prompt='Google Spreadsheet ID', help='ID from spreadsheet URL')
@click.option('--worksheet-name', default='WorkTime', help='Worksheet name (default: WorkTime)')
def add_google(credentials_file, spreadsheet_id, worksheet_name):
    """
    Добавить Google credentials из JSON файла.
    
    CREDENTIALS_FILE: Путь к service_account.json файлу
    """
    print_header("Adding Google Credentials")
    
    try:
        # Прочитать credentials
        with open(credentials_file, 'r') as f:
            credentials_json = f.read()
        
        # Валидация
        if not validate_google_credentials(credentials_json):
            print_error("Invalid credentials file!")
            sys.exit(1)
        
        print_success("Credentials file validated")
        
        # Загрузить текущий конфиг
        config = load_config()
        
        # Обновить Google секцию
        config['google'] = {
            'spreadsheet_id': spreadsheet_id.strip(),
            'worksheet_name': worksheet_name.strip(),
            'credentials_json': credentials_json
        }
        
        # Сохранить
        save_config(config)
        
        click.echo()
        print_success("Google credentials added successfully! ✅")
        click.echo()
        print_info(f"Spreadsheet ID: {spreadsheet_id}")
        print_info(f"Worksheet: {worksheet_name}")
        
        # Безопасность: предложить удалить исходный файл
        click.echo()
        if click.confirm(
            f"⚠️  For security, do you want to delete the original file?\n"
            f"   {credentials_file}"
        ):
            os.remove(credentials_file)
            print_success(f"Deleted: {credentials_file}")
            print_info("Credentials are now safely stored in encrypted config")
        
    except Exception as e:
        print_error(f"Failed to add Google credentials: {e}")
        sys.exit(1)


@cli.command()
@click.option('--token', prompt='Telegram Bot Token', hide_input=True, help='Token from @BotFather')
@click.option('--chat-id', prompt='Admin Chat ID (optional, press Enter to skip)', default='', help='Your Telegram user ID')
def add_telegram(token, chat_id):
    """
    Добавить Telegram bot credentials.
    
    Получить токен: @BotFather → /newbot
    Узнать chat ID: @userinfobot
    """
    print_header("Adding Telegram Credentials")
    
    try:
        # Валидация токена
        if not validate_telegram_token(token):
            print_error("Invalid Telegram token!")
            sys.exit(1)
        
        print_success("Token validated")
        
        # Загрузить текущий конфиг
        config = load_config()
        
        # Обновить Telegram секцию
        config['telegram'] = {
            'bot_token': token.strip(),
            'admin_chat_id': chat_id.strip() if chat_id else None
        }
        
        # Сохранить
        save_config(config)
        
        click.echo()
        print_success("Telegram credentials added successfully! ✅")
        
        if chat_id:
            print_info(f"Admin Chat ID: {chat_id}")
        else:
            print_warning("Admin Chat ID not set. Notifications will be disabled.")
        
    except Exception as e:
        print_error(f"Failed to add Telegram credentials: {e}")
        sys.exit(1)


@cli.command()
def show():
    """
    Показать текущую конфигурацию (без секретов).
    """
    print_header("Current Configuration")
    
    try:
        config = load_config()
        
        # Google
        click.echo(click.style("📊 Google Sheets:", fg='cyan', bold=True))
        if config['google']:
            click.echo(f"  Spreadsheet ID: {config['google'].get('spreadsheet_id', 'Not set')}")
            click.echo(f"  Worksheet: {config['google'].get('worksheet_name', 'Not set')}")
            click.echo(f"  Credentials: {'✅ Set' if config['google'].get('credentials_json') else '❌ Not set'}")
        else:
            click.echo("  ❌ Not configured")
        
        click.echo()
        
        # Telegram
        click.echo(click.style("🤖 Telegram Bot:", fg='cyan', bold=True))
        if config['telegram']:
            token = config['telegram'].get('bot_token', '')
            if token:
                masked_token = token[:10] + '...' + token[-10:] if len(token) > 20 else '***'
                click.echo(f"  Token: {masked_token}")
            else:
                click.echo("  Token: ❌ Not set")
            
            chat_id = config['telegram'].get('admin_chat_id')
            click.echo(f"  Admin Chat ID: {chat_id if chat_id else '❌ Not set'}")
        else:
            click.echo("  ❌ Not configured")
        
        click.echo()
        
        # Sync settings
        click.echo(click.style("🔄 Synchronization:", fg='cyan', bold=True))
        sync = config.get('sync', {})
        click.echo(f"  Interval: {sync.get('interval', 30)}s")
        click.echo(f"  Batch size: {sync.get('batch_size', 20)}")
        click.echo(f"  Max attempts: {sync.get('max_attempts', 5)}")
        click.echo(f"  Conflict strategy: {sync.get('conflict_strategy', 'last_write_wins')}")
        
        click.echo()
        
        # Security
        click.echo(click.style("🔐 Security:", fg='cyan', bold=True))
        security = config.get('security', {})
        click.echo(f"  DB encryption: {'✅ Enabled' if security.get('db_encryption_enabled', True) else '❌ Disabled'}")
        click.echo(f"  Config file: {CONFIG_FILE}")
        click.echo(f"  Keyring service: {KEYRING_SERVICE}")
        
    except Exception as e:
        print_error(f"Failed to load config: {e}")
        sys.exit(1)


@cli.command()
def verify():
    """
    Проверить конфигурацию на корректность.
    """
    print_header("Configuration Verification")
    
    try:
        # Проверка encryption key
        click.echo("Checking encryption key...", nl=False)
        key = get_encryption_key()
        if key:
            print_success(" OK")
        else:
            print_error(" NOT FOUND")
            print_info("Run 'wtt-setup init' to create encryption key")
            sys.exit(1)
        
        # Проверка config file
        click.echo("Checking config file...", nl=False)
        if CONFIG_FILE.exists():
            print_success(" OK")
        else:
            print_error(" NOT FOUND")
            sys.exit(1)
        
        # Загрузка конфига
        click.echo("Loading config...", nl=False)
        config = load_config()
        print_success(" OK")
        
        # Проверка Google credentials
        click.echo("Checking Google credentials...", nl=False)
        if config['google'].get('spreadsheet_id') and config['google'].get('credentials_json'):
            print_success(" OK")
        else:
            print_warning(" INCOMPLETE")
            print_info("Run 'wtt-setup add-google' to add credentials")
        
        # Проверка Telegram
        click.echo("Checking Telegram credentials...", nl=False)
        if config['telegram'].get('bot_token'):
            print_success(" OK")
        else:
            print_warning(" NOT SET")
            print_info("Run 'wtt-setup add-telegram' to add token")
        
        click.echo()
        print_success("Configuration verification completed! ✅")
        
    except Exception as e:
        print_error(f"Verification failed: {e}")
        sys.exit(1)


@cli.command()
def rotate_key():
    """
    Ротация ключа шифрования.
    
    Создает новый ключ и перешифровывает конфигурацию.
    """
    print_header("Encryption Key Rotation")
    
    print_warning("This will create a new encryption key and re-encrypt your config.")
    if not click.confirm("Do you want to continue?"):
        print_info("Key rotation cancelled.")
        return
    
    try:
        # Загрузить конфиг со старым ключом
        click.echo("Loading config with old key...", nl=False)
        config = load_config()
        print_success(" OK")
        
        # Сгенерировать новый ключ
        click.echo("Generating new encryption key...", nl=False)
        new_key = Fernet.generate_key().decode()
        print_success(" OK")
        
        # Сохранить новый ключ
        click.echo("Storing new key in keyring...", nl=False)
        set_encryption_key(new_key)
        print_success(" OK")
        
        # Перешифровать конфиг с новым ключом
        click.echo("Re-encrypting config...", nl=False)
        save_config(config)
        print_success(" OK")
        
        click.echo()
        print_success("Encryption key rotated successfully! ✅")
        
    except Exception as e:
        print_error(f"Key rotation failed: {e}")
        sys.exit(1)


@cli.command()
def export_ci():
    """
    Экспорт конфигурации для CI/CD (GitHub Actions).
    
    Выводит переменные окружения для добавления в GitHub Secrets.
    """
    print_header("Export for CI/CD")
    
    try:
        config = load_config()
        
        click.echo("Add the following secrets to your GitHub repository:")
        click.echo("(Settings → Secrets and variables → Actions → New repository secret)")
        click.echo()
        
        # Google
        if config['google'].get('spreadsheet_id'):
            click.echo(click.style("SPREADSHEET_ID=", fg='green') + config['google']['spreadsheet_id'])
        
        if config['google'].get('worksheet_name'):
            click.echo(click.style("WORKSHEET_NAME=", fg='green') + config['google']['worksheet_name'])
        
        if config['google'].get('credentials_json'):
            # Для GitHub Secrets нужно передать JSON как строку
            creds_json = config['google']['credentials_json']
            click.echo(click.style("GOOGLE_CREDENTIALS_JSON=", fg='green'))
            click.echo(creds_json)
        
        click.echo()
        
        # Telegram
        if config['telegram'].get('bot_token'):
            click.echo(click.style("TELEGRAM_BOT_TOKEN=", fg='green') + config['telegram']['bot_token'])
        
        if config['telegram'].get('admin_chat_id'):
            click.echo(click.style("TELEGRAM_ADMIN_CHAT_ID=", fg='green') + config['telegram']['admin_chat_id'])
        
        click.echo()
        print_info("Copy-paste these values to GitHub Secrets")
        
    except Exception as e:
        print_error(f"Export failed: {e}")
        sys.exit(1)


@cli.command()
def reset():
    """
    Сбросить всю конфигурацию (ОПАСНО!).
    
    Удаляет:
    - Ключ шифрования из keyring
    - Файл конфигурации
    """
    print_header("Reset Configuration")
    
    print_warning("⚠️  WARNING: This will DELETE all your configuration!")
    print_warning("⚠️  You will need to run 'wtt-setup init' again.")
    
    if not click.confirm("Are you ABSOLUTELY sure?"):
        print_info("Reset cancelled.")
        return
    
    try:
        # Удалить ключ из keyring
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
            print_success("Deleted encryption key from keyring")
        except keyring.errors.PasswordDeleteError:
            print_warning("Encryption key not found in keyring")
        
        # Удалить файл конфигурации
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print_success(f"Deleted config file: {CONFIG_FILE}")
        else:
            print_warning("Config file not found")
        
        click.echo()
        print_success("Configuration reset completed!")
        click.echo()
        print_info("To set up again, run: wtt-setup init")
        
    except Exception as e:
        print_error(f"Reset failed: {e}")
        sys.exit(1)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    cli()
