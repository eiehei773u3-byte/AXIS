import asyncio
import json
import os
import time
import discord
from discord import app_commands
from discord.ext import commands
import requests
from ai import start_ai, is_whitelisted


# ------------------------------------------------------------------
# 1. ПРОВЕРКА И ЗАГРУЗКА ТОКЕНА
# ------------------------------------------------------------------
print("-=     start     =-")
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
RESET  = "\033[0m" 
print("setting")

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
    
    
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
# 3. Команды выключения (?exit / ?stop)
async def shutdown_bot(ctx):
    await ctx.send("Бот остановлен")
    await bot.change_presence(status=discord.Status.offline)
    await asyncio.sleep(1)
    await bot.close()
    
@bot.command(name="exit")
async def bot_exit(ctx):
    if not is_whitelisted(ctx.author.id):
        return
    await shutdown_bot(ctx)

@bot.command(name="stop")
async def bot_stop(ctx):
    if not is_whitelisted(ctx.author.id):
        return
    await shutdown_bot(ctx)













@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    await bot.tree.sync()

async def main():
    await bot.start(token)
    asyncio.create_task(start_ai())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[СТАТУС] Бот переведён в статус 'Невидимый' и выключен.")