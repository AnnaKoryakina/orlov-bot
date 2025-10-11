# orlov_bot.py
# Бот Майора Орлова — живая версия с юмором и финальной синхронизацией с Центром

import os, re, random, asyncio, logging, aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackContext, filters
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

# ===== ПОДОЗРИТЕЛЬНЫЙ РЕЖИМ =====
SUS_TRIGGERS = re.compile(r"(?:\b2023\b|\borl[_\-]?\s*417\b|\bиспытан\w*)", re.IGNORECASE)
SUS_REPLIES = [
    "Не туда смотришь.",
    "Тема закрыта. Возвращайся к текущему.",
    "Лишний вопрос.",
    "Кто подкинул? Оставь.",
    "Закрой этот хвост.",
    "Это было давно. И не с тобой.",
    "Мы об этом не говорим. Особенно вслух.",
    "Система не любит, когда ковыряются в старых логах.",
    "Если бы это было важно, я бы не молчал. Наверное.",
    "Ошибки прошлого не исправляются вопросами.",
    "Кто-то очень хочет воскресить старую историю. Не ты ли?",
    "Файл закрыт. Архив под грифом.",
    "Не тот момент для ностальгии.",
    "Снова в прошлое лезешь? Ты мазохист или историк?",
    "Резонанс не забывает, даже если ты забыл.",
    "Было. Устранили. Идём дальше.",
    "Проверка прошла… не идеально. Доволен?",
    "Я бы сказал, что это совпадение, если бы верил в совпадения.",
    "Ты спрашиваешь, как будто не знаешь, чем это кончилось.",
    "Зря ты туда полез. Серьёзно.",
    "Там, где были испытания, остались следы. Лучше не трогай.",
    "От этого вопроса у системы пульс растёт.",
    "Не лезь в старые логи. Они кусаются."
]

SUS_CHIRPS = ["Коротко.", "По делу.", "Без лирики.", "Не распыляйся."]

# ===== ПОДСТЁБЫ =====
TEASE_WRONG = [
    "Серьёзно? Даже система смутилась.",
    "Код не прошёл. Видимо, ты — тоже.",
    "Не туда. Даже не близко.",
    "Если бы за каждую ошибку платили, ты бы уже уехал на пенсию.",
    "Хорошая попытка. Плохой результат.",
    "Не об этом мы договаривались.",
    "А вот это уже искусство промаха.",
    "Ты хотя бы рядом стоял с нужным ответом?",
    "Смело, но мимо.",
    "Это было больно даже для логов.",
    "Даже Резонанс фыркнул от такого ввода.",
    "Хм… интересный способ ничего не угадать.",
    "Не-а. Но настроение поднял, спасибо.",
    "Так, ладно, давай сделаем вид, что этого не было.",
    "Вот и зачем ты это сделал?",
    "Не та частота. Совсем не та.",
    "Сеть ответила тебе молчанием. Это намёк.",
    "Ты сейчас серьёзно?",
    "Уверен, ты просто проверяешь моё терпение.",
    "Почти! — если считать, что ‘почти’ это 10 километров мимо.",
    "Логика — твой враг, видимо.",
    "Мозг включаем… теперь… теперь поздно.",
    "Результат: минус два балла к уверенности в тебе.",
    "Если это шутка — поставлю плюс за смелость.",
    "Ошибки бывают у всех. У тебя — чаще.",
    "Так. Ты просто хотел услышать мой голос, да?",
    "Это… было что угодно, кроме правильного ответа.",
    "Вот сейчас я даже не знаю, смеяться или плакать.",
    "Не волнуйся, Центр любит отчёты об ошибках.",
    "Мимо. Прямо в никуда.",
    "Ладно, попробуй снова. Только без фокусов.",
    "Почти попал… но это было ‘почти’ уровня анекдота.",
    "Данные зафиксированы. Стыд — тоже.",
    "Интересный выбор. Ошибочный, но интересный.",
    "Ну, хоть клавиатура работает — уже плюс.",
    "Даже автоисправление вздохнуло.",
    "Если это был тест на моё терпение — ты победил.",
    "Резонанс шумит от стыда.",
    "Я ничего не видел, ничего не слышал. Попробуй заново.",
    "Угу. Конечно. А теперь — правильный вариант."
]

TEASE_WRONG_SUS = [
    "Ты уверен, что работаешь на нас?",
    "Интересно… кому ты это показываешь?",
    "Ошибка. Или прикрытие?",
    "Смело. Опасно. Глупо.",
    "Фиксирую странную активность. Опять ты.",
    "Забавно. Прямо как отчёт в далеком 2009-м.",
    "Ты сейчас вводишь код или оправдываешься?",
    "Это не ответ. Это повод насторожиться.",
    "Записал. Потом обсудим.",
    "Хочешь проверить, насколько у меня хорошая память?",
    "Вот с этого места и начинаются утечки.",
    "Либо ошибка, либо тест. Либо предательство. Уточни.",
    "Такое чувство, будто ты пишешь не мне.",
    "Секунду… проверяю, ты ли это вообще.",
    "Бот не нервничает, но я — почти.",
    "Ой. Это было громко для системы слежения.",
    "Странный ввод. Или ты решил пошутить?",
    "Так. Это мы оставим для допроса.",
    "Ага. Код уровня 'я не виноват'.",
    "С каждой ошибкой ты всё больше похож на отчёт об инциденте."
]

ARRIVE_Q = re.compile(r"\b(на\s*месте|у\s*сарая|мы\s*здесь|мы\s*тут)\b", re.IGNORECASE)

# ===== СОСТОЯНИЕ =====
def get_stage(ctx): return ctx.chat_data.get("stage", 1)
def set_stage(ctx, n): ctx.chat_data["stage"] = n
def mark_sus(ctx, v=True): ctx.chat_data["sus"] = v

# ===== ПРИВЕТСТВИЕ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_stage(context, 1)
    mark_sus(context, False)
    context.application.bot_data.setdefault("center_ok_users", set())
    await update.message.reply_text("Привет. Связь есть. Рад снова видеть.")
    await asyncio.sleep(1)
    await update.message.reply_text("Обещаю — сегодня без пожарных тревог... почти.")
    await asyncio.sleep(1)
    await update.message.reply_text("Напиши, когда будешь на месте.")

# ===== СЛУЖЕБНЫЕ КОМАНДЫ =====
async def center_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.application.bot_data.setdefault("center_ok_users", set()).add(user_id)
    await update.message.reply_text("Принял метку от Центра.")

# ===== УВЕДОМЛЕНИЕ ЦЕНТРА =====
async def notify_center_orlov_received(user_id: int):
    url = os.getenv("CENTER_MARK_URL", "").strip()
    secret = os.getenv("SHARED_SECRET", "")
    if not url or not secret:
        return
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            await s.post(url, json={"user_id": user_id, "secret": secret})
    except Exception as e:
        log.warning(f"notify_center_orlov_received failed: {e}")

# ===== ФИНАЛЬНАЯ ПРОВЕРКА =====
async def final_check_job(context: CallbackContext):
    chat_id = context.job.chat_id
    user_id = context.job.data.get("user_id")
    center_set = context.application.bot_data.get("center_ok_users", set())
    if user_id in center_set:
        text = ("На два фронта играете? Знаете, агенты, как говорится — на двух стульев… двух зайцев… и всё такое.\n"
                "Это была проверка. Мы пересмотрим ваш допуск к программе.")
    else:
        text = "Красотки! Это была проверка и вы её прошли. Нельзя вестись на провокации."
    await context.bot.send_message(chat_id=chat_id, text=text)

# ===== ОБРАБОТКА ТЕКСТА =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    tl = t.lower()

    # Метка от Центра (HTTP-уведомление)
    if norm(t) in {"центр:внутренний", "центр: внутренний"}:
        user_id = update.effective_user.id
        context.application.bot_data.setdefault("center_ok_users", set()).add(user_id)
        await update.message.reply_text("Отмечено.")
        return

    # SUS режим
    if SUS_TRIGGERS.search(t):
        mark_sus(context, True)
        await update.message.reply_text(random.choice(SUS_REPLIES))
        return
    if context.chat_data.get("sus") and random.random() < 0.3:
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
            set_stage(context, 2)
            return
        await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    if stage == 2:
        if RE_GRAFFITI_BASE.search(t) or RE_GRAFFITI_ITALY.search(t):
            await update.message.reply_text(
                "Италия… эх, пора в отпуск. Проверил по архивам — вот следующая точка: 55.936601, 37.818231"
            )
            await asyncio.sleep(2)
            await update.message.reply_text("Здесь вам надо найти код. Это если вы забыли.")
            set_stage(context, 3)
            return
        await update.message.reply_text("Нет.")
        return

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
            set_stage(context, 4)
            return
        await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    if stage == 4:
        if is_valid_report_code(t):
            await update.message.reply_text(
                "В яблочко! Теперь сюда: 55.825414, 37.807408. Код — десятизначный."
            )
            set_stage(context, 5)
            return
        await update.message.reply_text("Мимо.")
        return

    if stage == 5:
        if is_valid_bunker_code(t):
            await update.message.reply_text(
                "Ага, получилось. Финишная прямая, собрались.\n"
                "55.823459, 37.805408\n\n"
                "Изъять объект — одному, максимум двое. Подсказка: 4/8\n"
                "Жду финальный код."
            )
            set_stage(context, 6)
            return
        await update.message.reply_text("Нет.")
        return

    if stage == 6:
        if is_internal(t):
            user_id = update.effective_user.id
            await notify_center_orlov_received(user_id)
            await update.message.reply_text("Ответ зафиксирован системой. Идёт проверка. Ждите.")
            context.job_queue.run_once(
                final_check_job,
                when=180,
                chat_id=update.effective_chat.id,
                data={"user_id": user_id}
            )
            set_stage(context, 7)
            return
        await update.message.reply_text(random.choice(TEASE_WRONG))
        return

    await update.message.reply_text("На связи.")

# --- AIOHTTP запуск на PTB 21 ---
from aiohttp import web
from telegram import Update

async def center_mark_handler(request):
    app = request.app["application"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)

    if data.get("secret") != os.getenv("SHARED_SECRET"):
        return web.json_response({"ok": False}, status=403)

    try:
        user_id = int(data.get("user_id", 0))
    except Exception:
        return web.json_response({"ok": False}, status=400)

    app.bot_data.setdefault("center_ok_users", set()).add(user_id)
    return web.json_response({"ok": True})
    

# 🔹 Универсальный обработчик Telegram-вебхука
async def telegram_webhook(request: web.Request):
    app = request.app["application"]          # PTB Application
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)

    try:
        update = Update.de_json(data, app.bot)
    except Exception:
        return web.Response(status=400)

    # Передаём апдейт в PTB
    await app.process_update(update)
    return web.Response(text="OK")


# 🔹 post_init — установка вебхука на старте
async def _post_init(app):
    base = os.getenv("WEBHOOK_BASE", "").rstrip("/")
    token = app.bot.token
    url = f"{base}/{token}"
    # сбрасываем старый и устанавливаем новый вебхук
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url, allowed_updates=["message"])
    logging.getLogger("orlov").info(f"Webhook set to {url}")


# 🔹 Точка входа — запуск приложения
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан.")

    # Создаём приложение и прикручиваем post_init
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(_post_init)
        .build()
    )

    # Обработчики команд и текстов
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        # AIOHTTP сервер
    aio = web.Application()
    aio["application"] = app

    # маршруты
    aio.router.add_post(f"/{token}", telegram_webhook)
    aio.router.add_post("/center_mark", center_mark_handler)

    # --- управление жизненным циклом PTB через aiohttp ---
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

    # Запуск aiohttp-сервера
    web.run_app(aio, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    main()
