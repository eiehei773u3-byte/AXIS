import os
import sys
import subprocess
import zipfile
import urllib.request
import json

# Список необходимых сторонних библиотек
REQUIRED_PACKAGES = {
    "discord": "discord.py",
    "requests": "requests"
}

def ensure_pip():
    """Проверяет наличие pip, и если его нет — устанавливает автоматически."""
    try:
        import pip
        print("✅ Модуль pip обнаружен.")
    except ImportError:
        print("⚠️ Модуль pip не найден. Пытаемся установить pip автоматически...")
        try:
            get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
            script_path = "get-pip.py"
            
            print("📥 Скачивание установщика pip...")
            urllib.request.urlretrieve(get_pip_url, script_path)
            
            print("📦 Установка pip...")
            subprocess.check_call([sys.executable, script_path])
            
            if os.path.exists(script_path):
                os.remove(script_path)
                
            print("🎉 pip успешно установлен!")
        except Exception as e:
            print(f"❌ Не удалось автоматически установить pip: {e}")
            print("💡 Пожалуйста, установите Python с галочкой 'Add Python to PATH' и 'Install pip'.")
            sys.exit(1)

def check_and_install_dependencies():
    """Проверяет и устанавливает внешние зависимости."""
    ensure_pip()
    
    missing_packages = []

    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(pip_name)

    if missing_packages:
        print("\n🔍 Обнаружены отсутствующие библиотеки:")
        for pkg in missing_packages:
            print(f"  • {pkg}")
            
        user_choice = input("\nУстановить их прямо сейчас? (да/нет): ").strip().lower()
        
        if user_choice in ['да', 'd', 'yes', 'y']:
            print("\n⏳ Установка зависимостей...\n")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
            except:
                pass

            for pkg in missing_packages:
                print(f"📦 Установка {pkg}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                    print(f"✅ {pkg} успешно установлен.\n")
                except subprocess.CalledProcessError:
                    print(f"❌ Ошибка при установке {pkg}.")
                    sys.exit(1)
            
            print("🎉 Все библиотеки на месте!\n")
        else:
            print("🛑 Установка отменена.")
            sys.exit(0)
    else:
        print("✅ Все библиотеки уже установлены.\n")

def unpack_setup():
    """Распаковывает zip-архив."""
    archive_name = "setup.zip"
    if not os.path.exists(archive_name):
        print(f"⚠️ Архив '{archive_name}' не найден в папке со скриптом!")
        return

    print(f"📂 Распаковка {archive_name}...")
    try:
        with zipfile.ZipFile(archive_name, 'r') as zip_ref:
            zip_ref.extractall("./")
        print("🚀 Распаковка завершена успешно!\n")
    except Exception as e:
        print(f"❌ Ошибка распаковки: {e}")
        sys.exit(1)

def setup_bot_token():
    """Проверяет bot/bot_token.json и запрашивает токен, если он пустой."""
    token_path = os.path.join("bot", "bot_token.json")
    os.makedirs("bot", exist_ok=True)
    
    config_data = {}
    if os.path.exists(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            config_data = {}

    token = str(config_data.get("token", "")).strip()
    
    if not token:
        print("🔑 Токен бота не найден или пуст.")
        new_token = input("Введите токен вашего Discord бота: ").strip()
        
        config_data["token"] = new_token
        
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Токен успешно сохранен в `{token_path}`!\n")
    else:
        print("✅ Токен бота найден в конфигурации.\n")

def setup_configurations():
    """Проверяет bot/configurations.json и запрашивает Discord ID админа, если список whitelist пуст."""
    config_path = os.path.join("bot", "configurations.json")
    os.makedirs("bot", exist_ok=True)

    config_data = {"whitelist": []}

    # Чтение существующего файла
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            config_data = {"whitelist": []}

    # Гарантируем, что ключ 'whitelist' существует и является списком
    if "whitelist" not in config_data or not isinstance(
        config_data["whitelist"], list
    ):
        config_data["whitelist"] = []

    # Если whitelist пустой — запрашиваем ID
    if not config_data["whitelist"]:
        print("🛡️ Discord ID администратора не найден в whitelist.")
        new_id = input(
            "Введите ваш Discord ID для белого списка (админки): "
        ).strip()

        if new_id:
            # Сохраняем ID как строку (или используйте int(new_id), если вам нужны числа)
            config_data["whitelist"].append(new_id)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            print(f"✅ Discord ID ({new_id}) успешно добавлен в `{config_path}`!\n")
        else:
            print("⚠️ ID не был введен. Белый список оставлен пустым.\n")
    else:
        print("✅ Discord ID администратора найден")

def run_bot():
    """Запускает bot/bot.py."""
    bot_script = os.path.join("bot", "bot.py")
    
    if not os.path.exists(bot_script):
        print(f"❌ Файл `{bot_script}` не найден!")
        return

    print(f"🤖 Запуск бота ({bot_script})...\n" + "="*40 + "\n")
    try:
        subprocess.run([sys.executable, bot_script], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Бот завершил работу с ошибкой: {e}")

if __name__ == "__main__":
    # 1. Проверка и установка библиотек (pip, discord.py, requests)
    check_and_install_dependencies()
    
    # 2. Распаковка архива setup.zip
    unpack_setup()
    
    # 3. Проверка и заполнение bot/bot_token.json
    setup_bot_token()
    
    # 4. Проверка и заполнение bot/configurations.json
    setup_configurations()
    
    # 5. Запуск bot/bot.py
    run_bot()
