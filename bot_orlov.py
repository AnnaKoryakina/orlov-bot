# bot_orlov.py
import os
import re
import asyncio
import random
import logging
from typing import List

from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ---------- ЛОГИ ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orlov")

# ---------- Утилиты ----------
def norm(s: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (s or "").strip()).lower()

def only_digits(s: str) -> str:
    import re as _re
    return _re.sub(r"\D+", "", s or "")

def cyr_lat_variants(s: str) -> str:
    x = (s or "").strip().lower()
    x = x.replace("ва-3", "ba-3").replace("вa-3", "ba-3")
    return x

def set_stage(ctx: ContextTypes.DEFAULT_TYPE, n: int):
    ctx.chat_data["stage"] = n

def get_stage(ctx: ContextTypes.DEFAULT_TYPE) -> int:
    return int(ctx.chat_data.get("stage", 0))

def mark_sus(ctx: ContextTypes.DEFAULT_TYPE, v: bool = True):
    ctx.chat_data["sus"] = v

def is_center_ok(ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(ctx.chat_data.get("center_ok"))

def set_center_ok(ctx: ContextTypes.DEFAULT_TYPE, v: bool = True):
    ctx.chat_data["center_ok"] = v

# ---------- Стадии и валидаторы ----------
VALID_REF_1 = "ref=itl-486-217"
RE_GRAFFITI_BASE = re.compile(r"\bграффит[иы]\b", re.IGNORECASE)
RE_GRAFFITI_ITALY = re.compile(r"\bграффит[иы].*итал", re.IGNORECASE)
RE_GRUZ = re.compile(r"^грузчики(?:\s*/\s*переезды)?$", re.IGNORECASE)
PLACE_RE = re.compile(r"\b(на\s*месте|мы\s*на\s*месте|я\s*на\s*месте|мы\s*здесь|я\s*здесь|у\s*сарая|у\s*шеда|я\s*тут|мы\s*тут)\b", re.IGNORECASE)

def is_valid_report_code(s: str) -> bool:
    return cyr_lat_variants(s) == "ba-3/int-2025-12"

def is_valid_bunker_code(s: str) -> bool:
    return only_digits(s) == "001130077"

def is_internal(s: str) -> bool:
    return norm(s) == "внутренний"

# ---------- Подозрительный режим ----------
SUS_TRIGGERS = re.compile(
    r"(?:\b2023\b|\b23\s*год|\bиспытан\w*|\borl[_\-]?\s*417\b|\brz[\-_/]?\s*δ?\s*417\b)",
    re.IGNORECASE
)
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
SUS_CHIRPS = ["Коротко.", "По делу.", "Без лирики.", "Вернись к задаче."]

# ---------- Пулы ответов ----------
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
    "Угу. Конечно. А теперь — правильный вариант.",
    "На память фото сделаю? Нет. Попробуй ещё.",
    "Всё хорошо, кроме правильности.",
    "Это ответ из параллельной вселенной."
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
    "Красиво, но мимо.",
    "Сформулируй точнее."
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
    "Перепроверь.",
    "Мимо."
]
FUNNY_BUNKER_WRONG = [
    "Бункер таким не открывается.",
    "Это номер маршрутки?",
    "Не тот формат.",
    "Попробуй ещё раз — точно."
]

# ---------- Единый ответчик на «неверно» ----------
def _pick(pool: List[str], used: List[str]) -> str:
    cand = [x for x in pool if x not in used]
    if not cand:
        cand = pool[:]
    choice = random.choice(cand)
    used.append(choice)
    if len(used) > 5:
        used.pop(0)
    return choice

async def reply_wrong(update: Update, context: ContextTypes.DEFAULT_TYPE, *pools: List[str]):
    used = context.chat_data.setdefault("used_wrong_lines", [])
    merged: List[str] = []
    for p in pools:
        merged.extend(p)
    if not merged:
        merged = ["Мимо. Попробуй внимательнее."]
    await update.message.reply_text(_pick(merged, used))

# --- Финальная проверка через PTB JobQueue ---
FINAL_DELAY = int(os.getenv("FINAL_DELAY_SEC", "180"))

async def final_check_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет финал через FINAL_DELAY секунд.
    Берём флаг center_ok из application.chat_data для нужного chat_id.
    """
    chat_id = context.job.data["chat_id"]
    center_ok = bool(context.application.chat_data.get(chat_id, {}).get("center_ok"))

    if center_ok:
        text = ("На два фронта играете? Знаете, агенты, как говорится — "
                "на двух стульев… двух зайцев… и всё такое.\n"
                "Это была проверка. Мы пересмотрим ваш допуск к программе.")
    else:
        text = "Красотки! Это была проверка и вы её прошли. Нельзя вестись на провокации."
    await context.bot.send_message(chat_id=chat_id, text=text)

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.clear()  # важно для повторных прогонов
    set_stage(context, 0)
    mark_sus(context, False)
    set_center_ok(context, False)
    await update.message.reply_text("Привет. Связь есть. Рад снова видеть.")
    await asyncio.sleep(0.8)
    await update.message.reply_text("Напиши, когда будешь на месте.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.clear()
    await update.message.reply_text("Стадия и состояние сброшены. Введи /start и далее «на месте» на первой точке.")

# служебная метка от Центра (через чат)
async def center_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_center_ok(context, True)
    await update.message.reply_text("Отмечено.")

# ---------- Основной обработчик ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t_raw = update.message.text or ""
    t = t_raw.strip()
    tl = t.lower()
    stage = get_stage(context)

    # служебная метка центра через чат
    if norm(t) in {"центр:внутренний", "центр: внутренний"}:
        set_center_ok(context, True)
        await update.message.reply_text("Отмечено.")
        return

    # просьбы о помощи — подстёбы
    if any(w in tl for w in ["помог", "помощ", "подсказ", "что делать", "застрял", "не получается", "скажи куда", "куда идти"]):
        await update.message.reply_text(random.choice(TEASE_HELP))
        return

    # «резонанс»
    if norm(t) == "резонанс":
        await update.message.reply_text(random.choice(FUNNY_RESONANCE))
        return

    # подозрительный режим / 2023
    if SUS_TRIGGERS.search(t):
        mark_sus(context, True)
        await update.message.reply_text(random.choice(SUS_REPLIES))
        return
    if context.chat_data.get("sus") and random.random() < 0.30:
        await update.message.reply_text(random.choice(SUS_CHIRPS))
        return

    # ---------- Стадии ----------
    # 0: ждём подтверждение, что на первой локации
    if stage == 0:
        if PLACE_RE.search(t):
            await update.message.reply_text(
                "Получили предварительные данные по утечке.\n"
                "Источник мог оставлять следы в периферийных узлах — особенно тех, что не были синхронизированы с Резонансом.\n\n"
                "Начните с точки по координатам, указанным в пакете.\n"
                "Проверьте внутренние документы, особенно все упоминания ручных каналов и секторов.\n\n"
                "Вам нужно найти код последнего активного сектора. Без него система не примет отчёт."
            )
            set_stage(context, 1)
        else:
            await update.message.reply_text("Ок. Как будете на месте — так и пишите: «на месте».")
        return

    # 1: ждём ref=itl-486-217
    if stage == 1:
        if norm(t) == VALID_REF_1:
            await update.message.reply_text("ITL значит… Кажется это физическая точка. Нужно проверить? Есть идеи где искать?")
            await asyncio.sleep(5)
            await update.message.reply_text("И нет, Центр не оплачивает дальние путешествия. Это что-то локальное. Ищите в округе.")
            set_stage(context, 2)
        else:
            if tl.startswith("ref="):
                await reply_wrong(update, context, FUNNY_WRONG_REF, TEASE_WRONG)
            else:
                await reply_wrong(update, context, TEASE_WRONG, TEASE_CHATTER)
        return

    # 2: граффити (Италия)
    if stage == 2:
        if RE_GRAFFITI_BASE.search(t) or RE_GRAFFITI_ITALY.search(t):
            await update.message.reply_text("Италия… эх, кажется, пора в отпуск. Проверил по архивам и нашей базе, вот вам следующая точка с барского плеча. Удачи. 55.936601, 37.818231")
            await asyncio.sleep(2)
            await update.message.reply_text("Здесь вам надо найти код. Это если вы забыли.")
            set_stage(context, 3)
        else:
            await reply_wrong(update, context, FUNNY_REPORT_WRONG, TEASE_WRONG)
        return

    # 3: объявление «Грузчики»/«Грузчики/переезды»
    if stage == 3:
        if RE_GRUZ.fullmatch(t):
            await update.message.reply_text("О смене карьеры задумываетесь? Посмотрим, как пройдёт это дело, номер, может, и стоит сохранить. Но, код подошёл. Теперь вам вот сюда: 55.838187, 37.643057. На точку прибыть до 15:30. И без опозданий, знаю я вас.")
            await asyncio.sleep(3)
            await update.message.reply_text("Документы не забудьте. Не хватало, чтобы расследование прекратилось от того, что агентов упекли.")
            await asyncio.sleep(2)
            await update.message.reply_text("И да — опять нужен будет код. Заполучите документ, введите код, жду.")
            set_stage(context, 4)
        else:
            await reply_wrong(update, context, FUNNY_REPORT_WRONG, TEASE_WRONG)
        return

    # 4: отчёт BA-3/INT-2025-12
    if stage == 4:
        if is_valid_report_code(t):
            await update.message.reply_text("В яблочко! Теперь сюда, но точно определить источник не смогли, так что осмотритесь, 10-ти значный код. 55.825414, 37.807408")
            set_stage(context, 5)
        else:
            await reply_wrong(update, context, FUNNY_REPORT_WRONG, TEASE_WRONG)
        return

    # 5: бункер 0011300-77
    if stage == 5:
        if is_valid_bunker_code(t):
            await update.message.reply_text("Ага, получилось. Финишная прямая, собрались, сжали булочки.\n55.823459, 37.805408")
            await asyncio.sleep(2)
            await update.message.reply_text("Чтобы изъять следующий объект, отправьте одного, максимум двух людей. Подсказка: 4/8\nЖду финальный код.")
            set_stage(context, 6)
        else:
            await reply_wrong(update, context, FUNNY_BUNKER_WRONG, TEASE_WRONG)
        return

    # 6: финальный ответ «внутренний»
    if stage == 6:
        if is_internal(t):
            await update.message.reply_text("Ответ зафиксирован системой. Идёт проверка. Ждите.")
            # было:
# ctx_snapshot = dict(context.chat_data)
# asyncio.create_task(schedule_final_check(context.bot, update.effective_chat.id, ctx_snapshot))

# стало:
context.application.job_queue.run_once(
    final_check_job,
    when=FINAL_DELAY,
    data={"chat_id": update.effective_chat.id}
)
            set_stage(context, 7)
        else:
            await reply_wrong(update, context, TEASE_WRONG, TEASE_CHATTER)
        return

    # пост-финиш: общие подстёбы
    if random.random() < 0.40:
        await update.message.reply_text(random.choice(TEASE_CHATTER))
    else:
        await update.message.reply_text("На связи.")

# ---------- HTTP: Telegram webhook ----------
async def telegram_webhook(request: web.Request):
    app = request.app["application"]  # PTB Application
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)
    try:
        update = Update.de_json(data, app.bot)
    except Exception:
        return web.Response(status=400)
    await app.process_update(update)
    return web.Response(text="OK")

# ---------- HTTP: служебная метка от Центра ----------
async def center_mark_handler(request: web.Request):
    app = request.app["application"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "err": "bad json"}, status=400)

    try:
        user_id = int(data.get("user_id", 0))
    except Exception:
        return web.json_response({"ok": False, "err": "bad user_id"}, status=400)

    # опциональная проверка секрета
    want = os.getenv("SHARED_SECRET", "")
    got = request.headers.get("X-Shared-Secret", "")
    if want and want != got:
        return web.json_response({"ok": False, "err": "forbidden"}, status=403)

    chat = app.chat_data.get(user_id)
    if chat is None:
        app.chat_data[user_id] = {}
        chat = app.chat_data[user_id]
    chat["center_ok"] = True
    return web.json_response({"ok": True})

# ---------- main: вебхук на aiohttp ----------
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Укажи BOT_TOKEN в переменных окружения.")

    app = ApplicationBuilder().token(token).build()

    # хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("center_ok", center_ok_cmd))  # служебная
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def _post_init(ptb_app):
        base = os.getenv("WEBHOOK_BASE", "").rstrip("/")
        if not base:
            log.warning("WEBHOOK_BASE пуст. Укажи домен Railway.")
            return
        url = f"{base}/{token}"
        await ptb_app.bot.set_webhook(url, allowed_updates=["message"])
        log.info(f"Webhook set to {url}")

    app.post_init = _post_init  # type: ignore

    # aiohttp-приложение
    aio = web.Application()
    aio["application"] = app

    # маршруты
    aio.router.add_post(f"/{token}", telegram_webhook)
    aio.router.add_post("/center_mark", center_mark_handler)

    # жизненный цикл PTB под вебхук
    async def _on_startup(aio_app: web.Application):
        ptb = aio_app["application"]
        await ptb.initialize()
        await ptb.start()
        log.info("PTB Application initialized and started")

    async def _on_cleanup(aio_app: web.Application):
        ptb = aio_app["application"]
        await ptb.stop()
        await ptb.shutdown()
        log.info("PTB Application stopped and shutdown")

    aio.on_startup.append(_on_startup)
    aio.on_cleanup.append(_on_cleanup)

    # запуск aiohttp
    web.run_app(aio, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

if __name__ == "__main__":
    main()

