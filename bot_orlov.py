import os, re, random, asyncio, logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackContext, filters
)

# ===== Логирование =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orlov")

# ===== Утилиты =====
def norm(s): return re.sub(r"\s+", " ", (s or "").strip()).lower()
def only_digits(s): return re.sub(r"\D+", "", s or "")
def cyr_lat_variants(s):
    x = (s or "").strip().lower()
    return x.replace("ва-3", "ba-3").replace("вa-3", "ba-3")

# ===== Проверки =====
VALID_REF_1 = "ref=itl-486-217"
RE_GRAFFITI_BASE = re.compile(r"\bграффит[иы]\b", re.IGNORECASE)
RE_GRAFFITI_ITALY = re.compile(r"\bграффит[иы].*итал", re.IGNORECASE)
RE_GRUZ = re.compile(r"^грузчики(?:\s*/\s*переезды)?$", re.IGNORECASE)
def is_valid_report_code(s): return cyr_lat_variants(s) == "ba-3/int-2025-12"
def is_valid_bunker_code(s): return only_digits(s) == "001130077"  # принимает "0011300-77"
def is_internal(s): return norm(s) == "внутренний"

# ===== Подозрительный режим =====
SUS_TRIGGERS = re.compile(r"(?:\b2023\b|\b23\s*год|\bиспытан\w*|\borl[_\-]?\s*417\b|\brz[\-_/]?\s*Δ?\s*417\b)", re.IGNORECASE)
SUS_REPLIES = [
    "Не туда смотришь.","Тема закрыта.","Лишний вопрос.","Кто подкинул? Оставь.","Закрой этот хвост."
]
SUS_CHIRPS = ["Коротко.","По делу.","Без лирики.","Не распыляйся."]

# ===== Реплики =====
TEASE_WRONG = [
    "Серьёзно? Даже система смутилась.",
    "Мои-ж вы хорошие! Нет!",
    "А если ещё разок? И сейчас действительно подумать?",
    "Код не прошёл. Видимо, ты — тоже.",
    "Не туда. Даже не близко.",
    "Неверно! Wrong! falsch! Я еще на 7 языках сказать могу",
    "Если бы за каждую ошибку платили, ты бы уже уехал на пенсию."
]
TEASE_WRONG_SUS = ["Холодно.","Нет.","Близко не было.","Лишний след. Отбрось."]
TEASE_CHATTER = [
    "Говоришь красиво, но пользы — ноль.",
    "Если бы болтовня помогала делу, я бы уже молчал.",
    "По делу, агент. Или просто скучаешь?"
]
FUNNY_WRONG_REF = [
    "Это не код. Это творческий порыв.",
    "Код не принят. Протокол кашлянул.",
    "Похоже на пароль Wi-Fi. Нам нужен другой."
]
FUNNY_REPORT_WRONG = ["Не подтверждается.","Такого кода нет.","Нет.","Мимо-оооо."]
FUNNY_BUNKER_WRONG = ["Бункер таким не открывается.","Это номер маршрутки?","Не тот формат.","Нет."]

HELLOS_NORMAL = ["Привет. На связи.","Есть контакт.","Орлов. Тут."]
HELLOS_SUS = ["Связь.","Канал открыт.","Слышу."]

ARRIVE_Q = re.compile(
    r"\b(на\s*месте|у\s*сарая|я\s*тут|мы\s*тут|я\s*здесь|мы\s*здесь|мы\s*на\s*месте)\b",
    re.IGNORECASE
)

# ===== Состояние =====
def get_stage(ctx): return ctx.chat_data.get("stage", 1)
def set_stage(ctx, n): ctx.chat_data["stage"] = n
def mark_sus(ctx, v=True): ctx.chat_data["sus"] = v
def is_center_ok(ctx): return bool(ctx.chat_data.get("center_ok"))
def set_center_ok(ctx, v=True): ctx.chat_data["center_ok"] = v

# ===== Приветствие =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_stage(context,1); mark_sus(context,False); set_center_ok(context,False)
    context.chat_data["arrived"]=False
    first=random.choice([
        "На связи. Рад снова видеть.",
        "Привет. Связь есть. Рад снова видеть.",
        "Орлов на линии. Рад снова видеть."
    ])
    joke=random.choice([
        "Обещаю — сегодня без пожарных тревог... почти.",
        "Надеюсь, кофе ещё тёплый, потому что спокойного дня не будет.",
        "Если всё пойдёт по плану — значит, я что-то упустил."
    ])
    await update.message.reply_text(first)
    await asyncio.sleep(1.0)
    await update.message.reply_text(joke)
    await asyncio.sleep(0.6)
    await update.message.reply_text("Напиши, когда будешь на месте.")

async def center_ok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_center_ok(context,True)
    await update.message.reply_text("Принял.")

# ===== Финальная проверка =====
async def final_check_job(context: CallbackContext):
    chat=context.job.chat_id
    if is_center_ok(context):
        txt=("На два фронта играете? Знаете, агенты, как говорится — на двух стульев… двух зайцев… и всё такое.\n"
             "Это была проверка. Мы пересмотрим ваш допуск к программе.")
    else:
        txt="Красотки! Это была проверка и вы её прошли. Нельзя вестись на провокации."
    await context.bot.send_message(chat_id=chat,text=txt)

# ===== Основной обработчик =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t=(update.message.text or "").strip(); tl=t.lower()

    if norm(t) in {"центр:внутренний","центр: внутренний"}:
        set_center_ok(context,True); await update.message.reply_text("Отмечено."); return

    if SUS_TRIGGERS.search(t):
        mark_sus(context,True); await update.message.reply_text(random.choice(SUS_REPLIES)); return
    if context.chat_data.get("sus") and random.random()<0.3:
        await update.message.reply_text(random.choice(SUS_CHIRPS)); return

    if not context.chat_data.get("arrived") and ARRIVE_Q.search(t):
        context.chat_data["arrived"]=True
        await update.message.reply_text(
            "Получили предварительные данные по утечке.\n"
            "Источник мог оставлять следы в периферийных узлах — особенно тех, что не были синхронизированы с Резонансом.\n\n"
            "Начните с точки по координатам, указанным в пакете.\n"
            "Проверьте внутренние документы, особенно все упоминания ручных каналов и секторов.\n\n"
            "Вам нужно найти код последнего активного сектора. Без него система не примет отчёт."
        )
        return

    stage=get_stage(context)

    # --- 1. Сарай ---
    if stage==1:
        if norm(t)==VALID_REF_1:
            await update.message.reply_text(
                "ITL значит… Кажется это физическая точка. Нужно проверить? Есть идеи где искать?"
            )
            await asyncio.sleep(5)
            await update.message.reply_text(
                "И нет, Центр не оплачивает дальние путешествия. Это что-то локальное. Ищите в округе."
            )
            set_stage(context,2); return
        else:
            if tl.startswith("ref="): await update.message.reply_text(random.choice(FUNNY_WRONG_REF))
            else:
                if random.random()<0.2: await update.message.reply_text(random.choice(TEASE_CHATTER))
                else: await update.message.reply_text("Не то.")
        return

    # --- 2. Граффити ---
    if stage==2:
        if RE_GRAFFITI_BASE.search(t) or RE_GRAFFITI_ITALY.search(t):
            await update.message.reply_text(
                "Италия… эх, кажется, пора в отпуск. Проверил по архивам и нашей базе, "
                "вот вам следующая точка с барского плеча. Удачи. 55.936601, 37.818231"
            )
            await asyncio.sleep(2)
            await update.message.reply_text("Здесь вам надо найти код. Это если вы забыли.")
            set_stage(context,3); return
        else:
            if random.random()<0.2: await update.message.reply_text(random.choice(TEASE_CHATTER))
            else: await update.message.reply_text("Нет.")
        return

    # --- 3. Столб / Грузчики ---
    if stage==3:
        if RE_GRUZ.fullmatch(t):
            await update.message.reply_text(
                "О смене карьеры задумываетесь? Посмотрим, как пройдёт это дело, номер, может, и стоит сохранить. "
                "Но, код подошёл. Теперь вам вот сюда: 55.838187, 37.643057. На точку прибыть до 15:30. "
                "И без опозданий, знаю я вас."
            )
            await asyncio.sleep(3)
            await update.message.reply_text(
                "Документы не забудьте. Не хватало, чтобы расследование прекратилось от того, что агентов упекли."
            )
            await asyncio.sleep(5)
            await update.message.reply_text(
                "И опять нужен будет код. Заполучите документ, введите код, буду ждать."
            )
            set_stage(context,4); return
        else:
            await update.message.reply_text(
                random.choice(TEASE_WRONG if not context.chat_data.get('sus') else TEASE_WRONG_SUS)
            ); return

    # --- 4. Стрелковый клуб ---
    if stage==4:
        if is_valid_report_code(t):
            await update.message.reply_text(
                "В яблочко! Теперь сюда, но точно определить источник не смогли, "
                "так что осмотритесь, 10-ти значный код. 55.825414, 37.807408"
            )
            set_stage(context,5); return
        else: await update.message.reply_text(random.choice(FUNNY_REPORT_WRONG)); return

    # --- 5. Бункер ---
    if stage==5:
        if is_valid_bunker_code(t):
            await update.message.reply_text(
                "Ага, получилось. Финишная прямая, собрались, сжали булочки.\n"
                "55.823459, 37.805408\n\n"
                "Чтобы изъять следующий объект нужно отправить одного, максимум двух людей, вот подсказка. 4/8\n"
                "Жду финальный код."
            )
            set_stage(context,6); return
        else: await update.message.reply_text(random.choice(FUNNY_BUNKER_WRONG)); return

    # --- 6. Финал ---
    if stage==6:
        if is_internal(t):
            await update.message.reply_text("Ответ зафиксирован системой. Идёт проверка. Ждите.")
            context.job_queue.run_once(final_check_job,when=180,chat_id=update.effective_chat.id)
            set_stage(context,7); return
        else: await update.message.reply_text(random.choice(TEASE_WRONG)); return

    await update.message.reply_text("На связи.")

# ===== MAIN =====
def main():
    token=os.environ.get("BOT_TOKEN")
    if not token: raise RuntimeError("Укажи BOT_TOKEN в переменных окружения.")
    app=ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("center_ok",center_ok_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))

    base=os.getenv("WEBHOOK_BASE","").strip().rstrip("/")
    if base:
        path=f"/{token}"; url=f"{base}{path}"
        log.info(f"Starting webhook at {url}")
        app.run_webhook(listen="0.0.0.0",port=int(os.getenv("PORT","8080")),
                        url_path=path,webhook_url=url,drop_pending_updates=True)
    else:
        log.info("Starting polling (no WEBHOOK_BASE set)")
        app.run_polling(drop_pending_updates=True,close_loop=False)

if __name__=="__main__": main()
