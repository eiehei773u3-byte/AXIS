import asyncio
import json
import os
import time
import discord
from discord import app_commands
from discord.ext import commands
import requests

# ------------------------------------------------------------------
# 1. ПРОВЕРКА И ЗАГРУЗКА ТОКЕНА
# ------------------------------------------------------------------
print("start AI")
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
RESET  = "\033[0m" 

token = None

try:
    with open("bot_token.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if data.get("token"):
        token = data["token"]
        print(f"token [{GREEN}✓{RESET}]")
    else:
        print(f"token [{YELLOW}token not{RESET}]")

except FileNotFoundError:
    print(f"token [{RED}ERR{RESET}]")
except json.JSONDecodeError:
    print(f"token [{RED}ERR: invalid json{RESET}]")

if not token:
    print(f"{RED}Ошибка: Токен не найден. Завершение работы.{RESET}")
    exit()

# ------------------------------------------------------------------
# 2. НАСТРОЙКИ И ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ------------------------------------------------------------------
TEST_MODE = True  # True — тестовый режим, False — боевой с Ollama

MODEL_NAME = "gemma3:1b"
OLLAMA_URL = "http://localhost:11434/api/generate"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

# Очередь и блокировки
ollama_lock = asyncio.Lock()
waiting_users = []
current_generating_user = None

# ------------------------------------------------------------------
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (КОНФИГУРАЦИЯ И БАНЫ)
# ------------------------------------------------------------------
def get_whitelist() -> list:
    """Динамическое чтение белого списка из Configurations.json"""
    config_file = "Configurations.json"
    if not os.path.exists(config_file):
        # Создаем дефолтный файл, если его нет
        default_config = {"whitelist": [1151046802422910986]}
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            return default_config["whitelist"]
        except Exception as e:
            print(f"{RED}[CONFIG ERR] Не удалось создать Configurations.json: {e}{RESET}")
            return [1151046802422910986]

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            whitelist = data.get("whitelist", [])
            # Приводим к int
            return [int(x) for x in whitelist]
    except Exception as e:
        print(f"{RED}[CONFIG ERR] Ошибка чтения Configurations.json: {e}{RESET}")
        return []

def is_whitelisted(user_id: int) -> bool:
    """Проверка, находится ли пользователь в белом списке"""
    whitelist = get_whitelist()
    return user_id in whitelist

def is_user_banned(user_id: int) -> bool:
    ban_file = "ban.json"
    if not os.path.exists(ban_file):
        return False
    try:
        with open(ban_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return False
            banned_data = json.loads(content)
            target_id = str(user_id)
            if isinstance(banned_data, list):
                return target_id in [str(x).strip() for x in banned_data]
            elif isinstance(banned_data, dict):
                return target_id in [str(k).strip() for k in banned_data.keys()]
    except Exception as e:
        print(f"{RED}[BAN CHECK ERR] {e}{RESET}")
        return False
    return False

def add_user_to_ban(user_id: int) -> bool:
    ban_file = "ban.json"
    banned_list = []
    if os.path.exists(ban_file):
        try:
            with open(ban_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    banned_list = json.loads(content)
        except Exception:
            banned_list = []
    
    if user_id not in banned_list and str(user_id) not in banned_list:
        banned_list.append(user_id)
        with open(ban_file, "w", encoding="utf-8") as f:
            json.dump(banned_list, f, indent=4)
        return True
    return False

def remove_user_from_ban(user_id: int) -> bool:
    ban_file = "ban.json"
    if not os.path.exists(ban_file):
        return False
    try:
        with open(ban_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return False
            banned_list = json.loads(content)
        
        target_str = str(user_id)
        new_list = [x for x in banned_list if str(x).strip() != target_str]
        
        if len(new_list) != len(banned_list):
            with open(ban_file, "w", encoding="utf-8") as f:
                json.dump(new_list, f, indent=4)
            return True
    except Exception as e:
        print(f"Ошибка при разбане: {e}")
    return False

def get_ollama_response(prompt: str):
    start_time = time.time()
    if TEST_MODE:
        time.sleep(2)
        gen_time = round(time.time() - start_time, 2)
        return (
            f"\n```тестовое сообщение```\n\n"
            f"Время генерации ответа: `{gen_time}` сек"
        )

    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if res.status_code == 200:
            gen_time = round(time.time() - start_time, 2)
            ai_reply = res.json().get("response", "Пустой ответ.")
            return (
                f"\n{ai_reply}\n\n"
                f"Время генерации ответа: `{gen_time}` сек"
            )
        return f"Ошибка Ollama: status {res.status_code}"
    except Exception as e:
        return f"Ошибка запроса к Ollama: `{str(e)}`"

async def update_queue_positions():
    for index, item in enumerate(waiting_users):
        msg = item["status_msg"]
        u_id = item["user_id"]
        if msg:
            try:
                pos = index + 2
                await msg.edit(content=f"<@{u_id}>\nВы добавлены в очередь. Ваш номер: **#{pos}**")
            except Exception:
                pass



# ------------------------------------------------------------------
# 4. ОБРАБОТКА ЗАПРОСОВ И ОЧЕРЕДИ
# ------------------------------------------------------------------
async def process_ask_request(user_id: int, prompt: str, ctx_or_interaction, is_priority: bool = False):
    global current_generating_user
    try:
        # 1. ПРОВЕРКА НА БАН
        if is_user_banned(user_id):
            banned_msg = f"<@{user_id}>\nВы находитесь в бане и не можете использовать эту команду."
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(banned_msg)
            else:
                await ctx_or_interaction.response.send_message(banned_msg, ephemeral=True)
            return

        # 2. ПРОВЕРКА ОЧЕРЕДИ
        if ollama_lock.locked():
            item = {
                "user_id": user_id,
                "status_msg": None,
                "is_priority": is_priority,
                "cancel_event": asyncio.Event(),
                "channel": ctx_or_interaction.channel
            }

            if is_priority:
                waiting_users.insert(0, item)
            else:
                waiting_users.append(item)

            pos = (waiting_users.index(item)) + 2
            queue_text = f"<@{user_id}>\nВы добавлены в очередь. Ваш номер: **#{pos}**"

            if isinstance(ctx_or_interaction, commands.Context):
                status_msg = await ctx_or_interaction.send(queue_text)
            else:
                await ctx_or_interaction.response.send_message(queue_text)
                status_msg = await ctx_or_interaction.original_response()

            item["status_msg"] = status_msg

            if is_priority:
                await update_queue_positions()

            async with ollama_lock:
                if item["cancel_event"].is_set() or is_user_banned(user_id):
                    if item in waiting_users:
                        waiting_users.remove(item)
                    await update_queue_positions()
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    return

                if item in waiting_users:
                    waiting_users.remove(item)
                await update_queue_positions()

                current_generating_user = item
                try:
                    await status_msg.edit(content=f"<@{user_id}>\nДумает...")
                except Exception:
                    pass

                try:
                    response_text = await asyncio.to_thread(get_ollama_response, prompt)
                except Exception as e:
                    response_text = f"Ошибка генерации: `{e}`"
                finally:
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    current_generating_user = None

                if item["cancel_event"].is_set() or is_user_banned(user_id):
                    await item["channel"].send(f"<@{user_id}>\nВо время генерации вы были добавлены в бан-лист. Генерация остановлена.")
                else:
                    await item["channel"].send(f"<@{user_id}>\n{response_text}")

        # Если нейросеть свободна
        else:
            cancel_event = asyncio.Event()
            item = {
                "user_id": user_id,
                "cancel_event": cancel_event,
                "channel": ctx_or_interaction.channel
            }

            if isinstance(ctx_or_interaction, commands.Context):
                async with ctx_or_interaction.typing():
                    async with ollama_lock:
                        current_generating_user = item
                        response_text = await asyncio.to_thread(get_ollama_response, prompt)
                        current_generating_user = None

                        if cancel_event.is_set() or is_user_banned(user_id):
                            await ctx_or_interaction.send(f"<@{user_id}>\nВо время генерации вы были добавлены в бан-лист. Генерация остановлена.")
                        else:
                            await ctx_or_interaction.send(f"<@{user_id}>\n{response_text}")
            else:
                await ctx_or_interaction.response.defer(thinking=True)
                async with ollama_lock:
                    current_generating_user = item
                    response_text = await asyncio.to_thread(get_ollama_response, prompt)
                    current_generating_user = None

                    if cancel_event.is_set() or is_user_banned(user_id):
                        await ctx_or_interaction.followup.send(f"<@{user_id}>\nВо время генерации вы были добавлены в бан-лист. Генерация остановлена.")
                    else:
                        await ctx_or_interaction.followup.send(f"<@{user_id}>\n{response_text}")

    except Exception as main_err:
        print(f"{RED}Критическая ошибка в process_ask_request: {main_err}{RESET}")

# ------------------------------------------------------------------
# 5. КОМАНДЫ БОТА
# ------------------------------------------------------------------

# 1. Текстовая команда ?ask
@bot.command(name="ask")
async def ask(ctx, *, prompt: str):
    is_prio = is_whitelisted(ctx.author.id)
    await process_ask_request(ctx.author.id, prompt, ctx, is_priority=is_prio)

# 2. Слэш-команда /ask
@bot.tree.command(name="ask", description="Задать вопрос Ollama")
@app_commands.describe(prompt="Ваш вопрос")
async def slash_ask(interaction: discord.Interaction, prompt: str):
    await process_ask_request(interaction.user.id, prompt, interaction, is_priority=False)

# 4. Слэш-команда /ban
@bot.tree.command(name="ban", description="Заблокировать пользователя по ID")
@app_commands.describe(user_id="ID пользователя (цифрами)")
async def slash_ban(interaction: discord.Interaction, user_id: str):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
        return

    try:
        target_id = int(user_id.strip())
    except ValueError:
        await interaction.response.send_message("Некорректный ID пользователя! Используйте цифры.", ephemeral=True)
        return

    added = add_user_to_ban(target_id)
    
    if current_generating_user and current_generating_user["user_id"] == target_id:
        current_generating_user["cancel_event"].set()

    for item in list(waiting_users):
        if item["user_id"] == target_id:
            item["cancel_event"].set()

    if added:
        await interaction.response.send_message(f"Пользователь с ID `{target_id}` успешно добавлен в бан-лист.")
    else:
        await interaction.response.send_message(f"Пользователь с ID `{target_id}` уже находится в бан-листе.")

# 5. Слэш-команда /unban
@bot.tree.command(name="unban", description="Разблокировать пользователя по ID")
@app_commands.describe(user_id="ID пользователя (цифрами)")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
        return

    try:
        target_id = int(user_id.strip())
    except ValueError:
        await interaction.response.send_message("Некорректный ID пользователя!", ephemeral=True)
        return

    removed = remove_user_from_ban(target_id)
    if removed:
        await interaction.response.send_message(f"Пользователь с ID `{target_id}` успешно разбанен.")
    else:
        await interaction.response.send_message(f"Пользователь с ID `{target_id}` не найден в бан-листе.")

# 6. Слэш-команда /banlist
@bot.tree.command(name="banlist", description="Показать список заблокированных пользователей")
async def slash_banlist(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
        return

    ban_file = "ban.json"
    if not os.path.exists(ban_file):
        await interaction.response.send_message("Бан-лист пуст.")
        return

    try:
        with open(ban_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            banned_data = json.loads(content) if content else []

        if not banned_data:
            await interaction.response.send_message("Бан-лист пуст.")
            return

        lines = ["**Список заблокированных пользователей (ID):**"]
        for b_id in banned_data:
            uid = str(b_id).strip()
            lines.append(f"`{uid}`")

        await interaction.response.send_message("\n".join(lines))
    except Exception as e:
        await interaction.response.send_message(f"Ошибка чтения бан-листа: `{e}`")

# ------------------------------------------------------------------
# 6. СОБЫТИЯ И ЗАПУСК
# ------------------------------------------------------------------
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    await bot.tree.sync()
    mode_str = f"{YELLOW}[ТЕСТОВЫЙ AI]{RESET}" if TEST_MODE else f"{GREEN}[AI]{RESET}"
    print(f"Бот {bot.user} запущен и готов к работе! {mode_str}")

async def start_ai():
    """Асинхронный запуск AI-бота для вызова из главного файла через await"""
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n[СТАТУС] Бот переведён в статус 'Невидимый' и выключен.")
    except Exception as e:
        print(f"{RED}[ОШИБКА ЗАПУСКА AI] {e}{RESET}")

if __name__ == "__main__":
    # Логика для прямого запуска ai.py (без импорта)
    try:
        asyncio.run(start_ai())
    except KeyboardInterrupt:
        print("\n[СТАТУС] Работа бота завершена.")
