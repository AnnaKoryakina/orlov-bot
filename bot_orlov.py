# bot_orlov_webhook.py
# Майор Орлов — версия для локального polling и Railway webhook.
# Логика: строгие ответы по этапам, подстёбы, "подозрительный" режим, финальная проверка "двойная игра".
# python-telegram-bot >= 20

import os
import re
import logging
import random
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackContext, filters
)

# ---------- ЛОГИ ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orlov")

# ---------- Утилиты ----------
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def cyr_lat_variants(s: str) -> str:
    x = (s or "").strip().lower()
    x = x.replace("ва-3", "ba-3").replace("вa-3", "ba-3")
    return x

# ---------- Скрытые проверки (этапы) ----------
VALID_REF_1 = "ref=itl-486-217"
RE_GRAFFITI_BASE = re.compile(r"\bграффит[иы]\b", re.IGNORECASE)
RE_GRAFFITI_ITALY = re.compile(r"\bграффит[иы].*итал", re.IGNORECASE)
RE_GRUZ = re.compile(r"^грузчики(?:\s*/\s*переезды)?$", re.IGNORECASE)

def is_valid_report_code(s: str) -> bool:
    return cyr_lat_variants(s) == "ba-3/int-2025-12"

def is_valid_bunker_code(s: str) -> bool:
    return only_digits(s) == "001130077"

def is_internal(s: str) -> bool:
    return norm(s) == "внутренний"

# ---------- Подозрительный режим ----------
SUS_TRIGGERS = re.compile(r"(?:\b2023\b|\b23\s*год|\bиспытан\w*|\borl[_\-]?\s*417\b|\brz[\-_/]?\s*Δ?\s*417\b)", re.IGNORECASE)
SUS_REPLIES = [
    "Не тот разговор, не то время.",
    "Эта тема закрыта.",
    "Работай по текущему.",
    "Кто тебе это подкинул?",
    "Закрывай вопрос."
]
SUS_CHIRPS = ["Коротко.", "По делу.", "Без лирики.", "Вернись к задаче."]

# ---------- Подстёбы ----------
TEASE_WRONG = [
    "Серьёзно? Даже система смутилась.",
    "Вот теперь я начинаю волноваться за твоё обучение.",
    "Код не прошёл. Видимо, ты — тоже.",
    "Если бы за каждую ошибку платили, ты бы уже уехал на пенсию.",
    "Не туда. Даже не близко.",
    "Давай попробуем с мозгами включёнными.",
    "Было больно смотреть.",
    "Нет. И это было предсказуемо.",
    "Ты уверен, что это не шифр Wi-Fi?",
    "Неплохо… если бы это было хоть немного похоже на ответ."
]
TEASE_CHATTER = [
    "Говоришь красиво, но пользы — ноль.",
    "Если бы болтовня помогала делу, я бы уже молчал.",
    "Ты сейчас пытаешься очаровать систему?",
    "Впечатляюще. Бесполезно, но впечатляюще.",
    "Меньше слов — больше пользы.",
    "Я слушаю, но не понимаю, зачем.",
    "Это всё, или будет что-то умное?",
    "По делу, агент. Или просто скучаешь?"
]
TEASE_HELP = [
    "Помощь? А, ну конечно, вдруг всё само решится.",
    "Это твоя работа, не моя.",
    "Я бы помог, но тогда кто из нас агент?",
    "Дыши. Читай. Думай. В этом порядке.",
    "Инструкции закончились ровно там, где начинается голова.",
    "Не плачь, агент, просто внимательнее смотри на бумагу.",
    "Тебе точно выдавали мозги при приёме в Центр?",
    "Если бы я подсказывал каждому — мы бы до сих пор искали сарай."
]
FUNNY_WRONG_REF = [
    "Это не код. Это творческий порыв.",
    "Код не принят. Протокол кашлянул.",
    "Похоже на пароль Wi-Fi клуба. Нам нужен другой.",
    "Нет. Попробуй снова — аккуратнее.",
    "Красиво, но мимо."
]
FUNNY_RESONANCE = [
    "Звучит солидно. Теперь — факты.",
    "Система кивает. Еле заметно.",
    "Хорошее слово. Ещё лучше — точный ввод.",
    "Резонанс резонирует. Коды — работают.",
    "Отмечено."
]
FUNNY_REPORT_WRONG = [
    "Не подтверждается.",
    "Такого кода нет в реестре.",
    "Нет.",
    "Перепроверь.",
    "Мимо."
]
FUNNY_BUNKER_WRONG = [
    "Бункер таким не открывается.",
    "Это номер маршрутки?",
    "Не тот формат.",
    "Нет.",
    "Попробуй ещё раз — точно."
]

# ---------- Состояние ----------
def get_stage(ctx: ContextTypes.DEFAULT_TYPE) -> int: 
    return ctx.chat_data.get("stage", 1)
def set_stage(ctx: ContextTypes.DEFAULT_TYPE, n: int):
    ctx.chat_data["stage"] = n
def mark_sus(ctx: ContextTypes.DEFAULT_TYPE, v: bool=True):
    ctx.chat_data["sus"] = v
def is_center_ok(ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(ctx.chat_data.get("center_ok"))
def set_center_ok(ctx: ContextTypes.DEFAULT_TYPE, v: bool=True):
    ctx.chat_data["center_ok"] = v

# ---------- Приветствие/служебные ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_stage(context, 1); mark_sus(context, False); set_center_ok(context, False)
    await update.message.reply_text("Привет. Связь есть. Я здесь.")

# пометить вручную, что «в другой бот» пришёл ответ (для ведущего или интеграции)
async def center_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_center_ok(context, True)
    await update.message.reply_text("Принял.")

# ---------- Финальная проверка (через 3 минуты) ----------
async def final_check_job(context: CallbackContext):
    chat_id = context.job.chat_id
    if is_center_ok(context):
        text = ("На два фронта играете? Знаете, агенты, как говорится — на двух стульев… двух зайцев… и всё такое.\n"
                "Это была проверка. Мы пересмотрим ваш допуск к программе.")
    else:
        text = "Красотки! Это была проверка и вы её прошли. Нельзя вестись на провокации."
    await context.bot.send_message(chat_id=chat_id, text=text)

# ---------- Основной обработчик ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    tl = t.lower()

    # Служебная метка через текст (для тестов/интеграции)
    if norm(t) in {"центр:внутренний", "центр: внутренний"}:
        set_center_ok(context, True); await update.message.reply_text("Отмечено."); return

    # Подозрительный режим по 2023/испытания
    if SUS_TRIGGERS.search(t):
        mark_sus(context, True); await update.message.reply_text(random.choice(SUS_REPLIES)); return
    if context.chat_data.get("sus") and random.random() < 0.30:
        await update.message.reply_text(random.choice(SUS_CHIRPS)); return

    # «резонанс» — отдельная реакция
    if norm(t) == "резонанс":
        await update.message.reply_text(random.choice(FUNNY_RESONANCE)); return

    # Просьбы о помощи — подстёбы, без подсказок
    if any(w in tl for w in ["помог", "помощ", "подсказ", "что делать", "застрял", "не получается", "скажи куда", "куда идти"]):
        await update.message.reply_text(random.choice(TEASE_HELP)); return

    stage = get_stage(context)

    # 1
    if stage == 1:
        if norm(t) == VALID_REF_1:
            await update.message.reply_text("Принял."); set_stage(context, 2)
        else:
            if tl.startswith("ref="):
                await update.message.reply_text(random.choice(FUNNY_WRONG_REF))
                if random.random() < 0.30: await update.message.reply_text(random.choice(TEASE_WRONG))
            else:
                if random.random() < 0.20:
                    await update.message.reply_text(random.choice(TEASE_CHATTER))
                else:
                    await update.message.reply_text("Не то.")
        return

    # 2
    if stage == 2:
        if RE_GRAFFITI_BASE.search(t) or RE_GRAFFITI_ITALY.search(t):
            await update.message.reply_text("Принял."); set_stage(context, 3)
        else:
            if random.random() < 0.20:
                await update.message.reply_text(random.choice(TEASE_CHATTER))
            else:
                await update.message.reply_text("Нет.")
        return

    # 3
    if stage == 3:
        if RE_GRUZ.fullmatch(t):
            await update.message.reply_text("Принял."); set_stage(context, 4)
        else:
            if random.random() < 0.30:
                await update.message.reply_text(random.choice(TEASE_WRONG))
            else:
                await update.message.reply_text("Мимо.")
        return

    # 4
    if stage == 4:
        if is_valid_report_code(t):
            await update.message.reply_text("Подтверждено."); set_stage(context, 5)
        else:
            await update.message.reply_text(random.choice(FUNNY_REPORT_WRONG))
            if random.random() < 0.30: await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    # 5
    if stage == 5:
        if is_valid_bunker_code(t):
            await update.message.reply_text("Принято."); set_stage(context, 6)
        else:
            await update.message.reply_text(random.choice(FUNNY_BUNKER_WRONG))
            if random.random() < 0.30: await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    # 6
    if stage == 6:
        if is_internal(t):
            await update.message.reply_text("Ответ зафиксирован системой. Идёт проверка. Ждите.")
            context.job_queue.run_once(final_check_job, when=180, chat_id=update.effective_chat.id)
            set_stage(context, 7)
        else:
            await update.message.reply_text("Нет.")
            if random.random() < 0.30: await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    # после финала — нейтрально, иногда подстёб на болтовню
    if random.random() < 0.20:
        await update.message.reply_text(random.choice(TEASE_CHATTER))
    else:
        await update.message.reply_text("На связи.")

# ---------- MAIN: polling локально / webhook для Railway ----------
def main():
    # Получаем токен из переменных окружения
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Укажи BOT_TOKEN в переменных окружения.")

    # Инициализация приложения Telegram
    app = ApplicationBuilder().token(token).build()

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("center_ok", center_ok_cmd))  # служебная команда
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Проверяем, есть ли адрес webhook
    base = os.getenv("WEBHOOK_BASE", "").strip().rstrip("/")
    if base:
        path = f"/{token}"
        url = f"{base}{path}"
        log.info(f"Starting webhook at {url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", "8080")),
            url_path=path,
            webhook_url=url,
            drop_pending_updates=True,
        )
    else:
        log.info("Starting polling (no WEBHOOK_BASE set)")
        app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
