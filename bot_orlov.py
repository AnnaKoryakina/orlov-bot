# orlov_bot.py
# Бот Майора Орлова — с подстёбами, подозрительным режимом и быстрым финалом

import os, re, random, asyncio, logging
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ===== ЛОГИ =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orlov")

# ===== УТИЛИТЫ =====
def norm(s): return re.sub(r"\s+", " ", (s or "").strip()).lower()
def only_digits(s): return re.sub(r"\D+", "", s or "")
def cyr_lat_variants(s):
    x = (s or "").strip().lower()
    return x.replace("ва-3", "ba-3").replace("вa-3", "ba-3")

# ===== ВАЛИДАТОРЫ =====
VALID_REF_1 = "ref=itl-486-217"
RE_GRAFFITI_BASE = re.compile(r"\bграффит[иы]\b", re.IGNORECASE)
RE_GRAFFITI_ITALY = re.compile(r"\bграффит[иы].*итал", re.IGNORECASE)
RE_GRUZ = re.compile(r"^грузчики(?:\s*/\s*переезды)?$", re.IGNORECASE)
def is_valid_report_code(s): return cyr_lat_variants(s) == "ba-3/int-2025-12"
def is_valid_bunker_code(s): return only_digits(s) == "001130077"
def is_internal(s): return norm(s) == "внутренний"

ARRIVE_Q = re.compile(r"\b(на\s*месте|у\s*сарая|мы\s*здесь|мы\s*тут|мы\s*на\s*месте|я\s*на\s*месте)\b", re.IGNORECASE)

# ===== СОСТОЯНИЕ =====
def get_stage(ctx): return ctx.chat_data.get("stage", 1)
def set_stage(ctx, n): ctx.chat_data["stage"] = n
def mark_sus(ctx, v=True): ctx.chat_data["sus"] = v

# ===== ПОДОЗРИТЕЛЬНЫЙ РЕЖИМ =====
SUS_TRIGGERS = re.compile(r"(?:\b2023\b|\borl[_\-]?\s*417\b|\bиспытан\w*|\bлог[ау]\b|\bпротокол\b)", re.IGNORECASE)
SUS_REPLIES = [
    "Не туда смотришь.", "Тема закрыта. Возвращайся к текущему.", "Лишний вопрос.",
    "Кто подкинул? Оставь.", "Закрой этот хвост.", "Это было давно. И не с тобой.",
    "Мы об этом не говорим. Особенно вслух.", "Система не любит, когда ковыряются в старых логах.",
    "Если бы это было важно, я бы не молчал. Наверное.", "Ошибки прошлого не исправляются вопросами.",
    "Кто-то очень хочет воскресить старую историю. Не ты ли?", "Файл закрыт. Архив под грифом.",
    "Не тот момент для ностальгии.", "Снова в прошлое лезешь? Ты мазохист или историк?",
    "Резонанс не забывает, даже если ты забыл.", "Было. Устранили. Идём дальше.",
    "Проверка прошла… не идеально. Доволен?", "Я бы сказал, что это совпадение, если бы верил в совпадения.",
    "Ты спрашиваешь, как будто не знаешь, чем это кончилось.", "Зря ты туда полез. Серьёзно.",
    "Там, где были испытания, остались следы. Лучше не трогай.", "От этого вопроса у системы пульс растёт.",
    "Не лезь в старые логи. Они кусаются."
]
SUS_CHIRPS = ["Коротко.", "По делу.", "Без лирики.", "Не распыляйся."]

# ===== ПОДСТЁБЫ (неверные ответы) =====
TEASE_WRONG = [
    "Серьёзно? Даже система смутилась.", "Код не прошёл. Видимо, ты — тоже.", "Не туда. Даже не близко.",
    "Если бы за каждую ошибку платили, ты бы уже уехал на пенсию.", "Хорошая попытка. Плохой результат.",
    "Не об этом мы договаривались.", "А вот это уже искусство промаха.", "Ты хотя бы рядом стоял с нужным ответом?",
    "Смело, но мимо.", "Это было больно даже для логов.", "Даже Резонанс фыркнул от такого ввода.",
    "Хм… интересный способ ничего не угадать.", "Не-а. Но настроение поднял, спасибо.",
    "Так, ладно, давай сделаем вид, что этого не было.", "Вот и зачем ты это сделал?",
    "Не та частота. Совсем не та.", "Сеть ответила тебе молчанием. Это намёк.", "Ты сейчас серьёзно?",
    "Уверен, ты просто проверяешь моё терпение.", "Почти! — если считать, что ‘почти’ это 10 километров мимо.",
    "Логика — твой враг, видимо.", "Мозг включаем… теперь… теперь поздно.",
    "Результат: минус два балла к уверенности в тебе.", "Если это шутка — поставлю плюс за смелость.",
    "Ошибки бывают у всех. У тебя — чаще.", "Так. Ты просто хотел услышать мой голос, да?",
    "Это… было что угодно, кроме правильного ответа.", "Вот сейчас я даже не знаю, смеяться или плакать.",
    "Не волнуйся, Центр любит отчёты об ошибках.", "Мимо. Прямо в никуда.",
    "Ладно, попробуй снова. Только без фокусов.", "Почти попал… но это было ‘почти’ уровня анекдота.",
    "Данные зафиксированы. Стыд — тоже.", "Интересный выбор. Ошибочный, но интересный.",
    "Ну, хоть клавиатура работает — уже плюс.", "Даже автоисправление вздохнуло.",
    "Если это был тест на моё терпение — ты победил.", "Резонанс шумит от стыда.",
    "Я ничего не видел, ничего не слышал. Попробуй заново.", "Угу. Конечно. А теперь — правильный вариант."
]

# ===== ПРИВЕТСТВИЕ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_stage(context, 1)
    mark_sus(context, False)
    await update.message.reply_text("Привет. Связь есть. Рад снова видеть.")
    await asyncio.sleep(1)
    await update.message.reply_text("Обещаю — сегодня без пожарных тревог... почти.")
    await asyncio.sleep(1)
    await update.message.reply_text("Напиши, когда будешь на месте.")

# ===== ОБРАБОТКА ТЕКСТА =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    tl = t.lower()

    # SUS режим — триггеры и периодические короткие уколы
    if SUS_TRIGGERS.search(t):
        mark_sus(context, True)
        await update.message.reply_text(random.choice(SUS_REPLIES))
        return
    if context.chat_data.get("sus") and random.random() < 0.30:
        await update.message.reply_text(random.choice(SUS_CHIRPS))
        return

    # Прибытие
    if ARRIVE_Q.search(t):
        if not context.chat_data.get("arrived"):
            context.chat_data["arrived"] = True
            await update.message.reply_text(
                "Получили предварительные данные по утечке.\n"
                "Источник мог оставлять следы в периферийных узлах.\n"
                "Начните с точки по координатам из пакета.\n"
                "Проверьте внутренние документы — ищем код последнего активного сектора."
            )
        else:
            await update.message.reply_text("Ушки на макушке, глаза ищут зацепки.")
        return

    stage = get_stage(context)

    # === ЭТАПЫ ===
    if stage == 1:
        if norm(t) == VALID_REF_1:
            await update.message.reply_text("ITL значит… Кажется это физическая точка. Нужно проверить? Есть идеи где искать?")
            await asyncio.sleep(5)
            await update.message.reply_text("И нет, Центр не оплачивает дальние путешествия. Это что-то локальное. Ищите в округе.")
            set_stage(context, 2); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    if stage == 2:
        if RE_GRAFFITI_BASE.search(t) or RE_GRAFFITI_ITALY.search(t):
            await update.message.reply_text("Италия… эх, пора в отпуск. Проверил по архивам — вот следующая точка: 55.936601, 37.818231")
            await asyncio.sleep(2)
            await update.message.reply_text("Здесь вам надо найти код. Это если вы забыли.")
            set_stage(context, 3); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    if stage == 3:
        if RE_GRUZ.fullmatch(t):
            await update.message.reply_text(
                "О смене карьеры задумываетесь? Посмотрим, как пройдёт это дело. "
                "Код подошёл. Теперь вот сюда: 55.838187, 37.643057. На точку прибыть до 15:30."
            )
            await asyncio.sleep(3)
            await update.message.reply_text("Документы не забудьте. Не хватало, чтобы расследование прекратилось от ареста.")
            await asyncio.sleep(5)
            await update.message.reply_text("И опять нужен будет код. Заполучите документ, введите код, буду ждать.")
            set_stage(context, 4); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    if stage == 4:
        if is_valid_report_code(t):
            await update.message.reply_text("В яблочко! Теперь сюда: 55.825414, 37.807408. Код — десятизначный.")
            set_stage(context, 5); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    if stage == 5:
        if is_valid_bunker_code(t):
            await update.message.reply_text(
                "Ага, получилось. Финишная прямая, собрались.\n"
                "55.823459, 37.805408\n\n"
                "Изъять объект — одному, максимум двое. Подсказка: 4/8\n"
                "Жду финальный код."
            )
            set_stage(context, 6); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    # === ФИНАЛ — «внутренний» сразу успех ===
    if stage == 6:
        if is_internal(t):
            await update.message.reply_text("Код принят. Миссия выполнена. Отличная работа, агент.")
            set_stage(context, 7); return
        await update.message.reply_text(random.choice(TEASE_WRONG)); return

    await update.message.reply_text("На связи.")

# ===== AIOHTTP И ВЕБХУК =====
async def telegram_webhook(request: web.Request):
    app = request.app["application"]
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    except Exception as e:
        log.exception("Webhook error: %s", e)
    return web.Response(text="OK")

async def _post_init(app):
    base = os.getenv("WEBHOOK_BASE", "").rstrip("/")
    token = app.bot.token
    if not base:
        log.warning("WEBHOOK_BASE не задан — вебхук не будет установлен.")
        return
    url = f"{base}/{token}"
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url, allowed_updates=["message"])
    log.info(f"Webhook set to {url}")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан.")

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    aio = web.Application()
    aio["application"] = app
    aio.router.add_post(f"/{token}", telegram_webhook)

    async def _on_startup(aio_app: web.Application):
        ptb_app = aio_app["application"]
        await ptb_app.initialize()
        await ptb_app.start()

    async def _on_cleanup(aio_app: web.Application):
        ptb_app = aio_app["application"]
        await ptb_app.stop()
        await ptb_app.shutdown()

    aio.on_startup.append(_on_startup)
    aio.on_cleanup.append(_on_cleanup)

    web.run_app(aio, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

if __name__ == "__main__":
    main()
