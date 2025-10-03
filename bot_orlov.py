# bot_orlov.py
import os
import random
import asyncio
from collections import deque
from datetime import time, datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    JobQueue,
    filters,
)


SARCASM_LEVEL = 2          
MAX_WRONG_STREAK = 2       # после N подряд неверных — стеб)))))

# реплики чтобы добавить животи, не забыть поменять время на 15 минут

IDLE_REPLIES = [
  
    "Слишком тихо вокруг... Держи ухо востро.",
    "Я тут пересмотрел досье ещё раз — кое-что не даёт покоя.",
    "Главное — не спеши. Ошибки нам сейчас ни к чему.",
    "Хм... иногда думаю, что у нас в отделе тоже есть крыса. Но это потом.",
    
    "Если вдруг заметишь хвост — предложи им булочку. Обычно работает.",
    "В штабе кофе снова закончился… Похоже, это диверсия.",
    "Ты не поверишь, но даже наша крыса опаздывает на работу.",
    "Будь осторожен. В прошлый раз агент чуть не провалился из-за кота. Серьезно.",
    "Говорят, секрет успеха — это дисциплина. Но я всё же за хороший кофе.",
    "Сегодня в столовой снова борщ разведданных. Кислый, но питательный.",
    "Если встретишь подозрительно вежливого голубя — шифруйся. Мы таких знаем.",
    "Отдышись и проверь документы. Дышать можно, паниковать — нельзя.",
]

# Варианты ответов на неверный ввод отредактировать и добавить смешные
WRONG_REPLIES = [
    "Принято. Но давай-ка только по делу, без воды. Это явно не зацепка. Жду от тебя сообщение с чем-то дельным.",
    "Принял, но это не похоже на полезную информацию. Пиши только по делу.",
    "Не отвлекай меня, агент. Нужны конкретные зацепки, а не болтовня.",
    "Хм… если это шифр, то даже наш аналитик из бухгалтерии его не понял.",
    "Агент, у меня сильное подозрение, что ты просто случайно нажал не те клавиши.",
    "Это точно не код. Но если бы был — я бы назвал его «Операция Совсем Не То».",
    "Агент, если это шифр, то он явно из раздела детских кроссвордов.",
    "Похоже на случайный набор букв… или у тебя кот прошёлся по клавиатуре?",
    "Прибор молчит. И я тоже постараюсь. Давай ещё раз, но по делу.",
    "Почти получилось! Если бы наша цель была — запутать Орлова.",
    "Так, я проверил… Это код от микроволновки. Нам нужен другой.",
    "Записал. Отправил в архив. В отдел шуток.",
    "Угу. Похоже на пароль от Wi-Fi. Есть что-то погорячее?",
    "Код интересный. Жалко, не наш.",
    "Если это зов о помощи — моргни два раза. Если код — набери ещё раз.",
    "С таким шифром я только чай могу заварить. Давай другое.",
    # Чуть ехиднее
    "Смело. Неверно — но смело. Продолжай в том же духе, только попадать начинай.",
    "Давай так: ты — ещё раз пробуешь, я — делаю вид, что не видел это сообщение.",
]

# длинные чтобы язык был живее
LONG_WRONG_REPLIES = [
    "Слушай… иногда мне кажется, что все это задание больше похоже на шахматную партию. "
    "Ходы продуманы заранее, а мы лишь пешки. Но пешка тоже может дойти до конца доски и превратиться в ферзя. "
    "Главное — не сдаться раньше времени.",
    "Знаешь, агент… за 20 лет службы я понял одну вещь: самые простые мелочи иногда переворачивают дело. "
    "Одна записка, одна забытая квитанция, одна случайная встреча. Так что не игнорируй детали.",
    "Когда я был на задании в 2007, всё пошло к черту. Связь оборвалась, координаты потерялись. "
    "Но одна странная надпись на стене вывела нас на цель. Так что, если увидишь что-то странное — лучше сфотографируй.",
]

# Коды 
CODES = {
    "777": (
        "Есть зацепка! Отправляйся по этим координатам "
        "55.901840, 37.713295.\n\n"
        "Тебе нужно прибыть на место до 10:00, это почему-то важно. "
        "Бери напарника и выезжай. Используйте свои имена, "
        "я позабочусь о прикрытии. Важно чтобы ни гражданские, "
        "ни бюро ничего не заподозрили. Удачи."
    ),
    "кукурузник": (
        "Верно! Вот новые координаты, срочно по следу! "
        "55.908373, 37.722586.\n\n"
        "Теперь этот приборчик просит длинный код… 11 цифр… или букв? Как знать."
    ),
    "89853019911": (
        "Хорошо! Отлично! Ты все ближе! "
        "55.911976,37.716748.\n\n"
        "Здесь нужно всего 4 буквы или цифры. Должно быть раз плюнуть. "
        "Особенно тебе."
    ),
    "1983": (
        "Финишная прямая, агент! "
        "55.903291, 37.712059.\n\n"
        "Но здесь была пометочка: «где-то тут, написать точные координаты потом». "
        "Кажется, кто-то не успел утвердить точку. Удачи!"
    ),
    "тайное свидание": (
        "Ага… интересно ты дело выполняешь, агент…\n"
        "Ладно, кажется, сработало. Тебе должны были передать папку. "
        "Нам кажется, что он с кем-то встречался неподалеку.\n"
        "Почитай информацию и отправляйся по следу.\n"
        "Пиши, когда будут новые зацепки."
    ),
    "парк": (
        "Кажется ты на верном месте. Теперь эта штуковина просит ответить на вопрос: "
        "«Какой самолет выберешь?» Есть идеи?"
    ),
    "бульвар": (
        "Кажется ты на верном месте. Теперь эта штуковина просит ответить на вопрос: "
        "«Какой самолет выберешь?» Есть идеи?"
    ),
    "бульвар ветеранов": (
        "Кажется ты на верном месте. Теперь эта штуковина просит ответить на вопрос: "
        "«Какой самолет выберешь?» Есть идеи?"
    ),
}

# Особые  ответы
SPECIAL_FUNNY = {
    "самолет": "Самолёт? Серьезно? Гениально, просто гениально. Думай ещё",
    "торт": "Торт — это святое. Но уликам нужнее крошки, чем нам калории 🎂",
    "не знаю": "Фраза, достойная отчёта. Но давай попробуем «узнаю» 😉",
    "нужна помощь": "Помощь уже выехала… на лошади. Может, пока сам справишься?",
    "ту": "«Ту-тууу» — это, конечно, локомотив. Но мы всё-таки агенты, а не машинисты 🚂",
    "спа": "СПА? Серьезно? Прохлаждаешься, агент? А ну работать!",
}

# Ответы на кофе
COFFEE_OK_WORDS = {"нормально", "вкусный", "хороший", "неплохой"}
COFFEE_JOKES = [
    "Отлично. Кофеин принят, мозги в строй! Возвращаемся к делу, агент.",
    "Записываю в протокол: кофе годен. А теперь — ноги в руки и вперёд!",
    "Кофе хороший — отмазки закончились. Включай режим «сокол».",
    "Принято. Если сердце не прыгает — значит, можно прыгать в работу.",
    "Вкусный? Тогда неси ещё зацепки. И мне капучино, если что.",
]

# доп функции и ответы
def sarcasm_on() -> bool:
    return SARCASM_LEVEL >= 2

def time_snark() -> str:
    h = datetime.now().hour
    if 0 <= h < 5:
        return "Ночной дозор, значит? Ладно. Смотри не усни на хвосте."
    if 5 <= h < 9:
        return "Ранний старт. Уважаю. Или кофе слишком крепкий?"
    if 22 <= h < 24:
        return "Поздновато для героизма, но кто я такой, чтобы мешать."
    return ""

async def type_then_reply(message, text: str, delay: float = 0.4):
    try:
        await message.chat.send_action(ChatAction.TYPING)
    except Exception:
        pass
    await asyncio.sleep(delay)
    await message.reply_text(text)

def choose_no_recent(options: list[str], history: deque, keep_last: int = 3) -> str:
    """Выбор фразы, избегая последних keep_last вариантов."""
    recent = set(list(history)[-keep_last:]) if history else set()
    pool = [o for o in options if o not in recent]
    if not pool:
        history.clear()
        pool = options[:]
    pick = random.choice(pool)
    history.append(pick)
    while len(history) > keep_last:
        history.popleft()
    return pick

# автоматизированные функции
# Авто-реплики (каждые 15–30 мин)
async def send_idle_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_data = context.chat_data
    idle_hist: deque = chat_data.setdefault("idle_hist", deque(maxlen=3))
    reply = choose_no_recent(IDLE_REPLIES, idle_hist, keep_last=3)
    try:
        await context.bot.send_message(job.chat_id, reply)
    except Exception:
        return
    delay = random.randint(900, 1800)  
    context.job_queue.run_once(send_idle_message, delay, chat_id=job.chat_id)

# Follow-up после 777 (10 мин!)
async def followup_after_777(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.send_message(
            job.chat_id,
            "Как только закончишь осмотр точки напиши название того, что там найдешь. "
            "Введу это в прибор, авось что-то покажет."
        )
    except Exception:
        return

# Follow-up после «тайное свидание» (20 мин!) посмотреть как сделать так чтобы болтовня не прерывала квест
async def followup_after_secret_meeting(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.send_message(
            job.chat_id,
            "Мы подтвердили, что он с кем-то встречался. Нужно понять где. "
            "Когда выяснишь, куда он пришел на встречу — дай знать."
        )
    except Exception:
        return

# КОФЕ: пинг в 11:47 МСК
async def send_coffee_ping(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    context.chat_data["awaiting_coffee_reply"] = True
    # сброс ожидания через 30 минут
    context.job_queue.run_once(clear_coffee_flag, when=1800, chat_id=job.chat_id)
    try:
        await context.bot.send_message(job.chat_id, "Ну как кофеек?")
    except Exception:
        return

async def clear_coffee_flag(context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["awaiting_coffee_reply"] = False

def schedule_daily_jobs(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    # удаляем старые задания на кофе для этого чата
    name = f"coffee_{chat_id}"
    for j in context.job_queue.get_jobs_by_name(name):
        j.schedule_removal()
    # план на 11:47 по Москве
    moscow = ZoneInfo("Europe/Moscow")
    context.job_queue.run_daily(
        send_coffee_ping,
        time=time(hour=11, minute=47, tzinfo=moscow),
        chat_id=chat_id,
        name=name,
    )

# ----------------- ХЕНДЛЕРЫ -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "Майор Орлов на связи. Рад видеть тебя, агент.\n"
        "Вводи коды или докладывай. Я проверю и дам инструкции."
    )
    # лёгкая ехидность по времени суток
    extra = time_snark()
    if sarcasm_on() and extra:
        await type_then_reply(update.message, extra, delay=0.2)

    # авто-реплики (через 15 минут) и ежедневный кофейный пинг
    context.job_queue.run_once(send_idle_message, 900, chat_id=chat_id)
    schedule_daily_jobs(chat_id, context)

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip().lower()

    # Кофе — ждём ответ?
    if context.chat_data.get("awaiting_coffee_reply"):
        if text in COFFEE_OK_WORDS:
            joke = random.choice(COFFEE_JOKES)
            if sarcasm_on():
                add = random.choice([
                    "Любитель компромиссов… Ладно, возвращаемся к делу.",
                    "Записываю: кофе ок, концентрация включена. Поехали.",
                    "Отлично. Теперь предлагаю заменить сахар на улики."
                ])
                joke = f"{joke}\n{add}"
            await type_then_reply(update.message, joke)
            context.chat_data["awaiting_coffee_reply"] = False
            return
        # если ответ другой — продолжаем как обычно

    # Приветствие
    if text in ["привет", "здравствуй", "добрый день", "привет!"]:
        await update.message.reply_text("Привет! Ну наконец-то! Я уже заждался. Рассказывай как дела.")
        return

    # Особые смешные ответы
    if text in SPECIAL_FUNNY:
        await type_then_reply(update.message, SPECIAL_FUNNY[text])
        return

    # Коды легенды
    if text in CODES:
        await type_then_reply(update.message, CODES[text])
        # сбрасываем серию ошибок при верном коде
        context.chat_data["wrong_streak"] = 0
        if text == "777":
            context.job_queue.run_once(followup_after_777, 600, chat_id=chat_id)
        if text == "тайное свидание":
            context.job_queue.run_once(followup_after_secret_meeting, 1200, chat_id=chat_id)
        return

    # Неверный ввод: серия + 10% длинный, иначе короткий/шутливый; без повторов
    wrong_hist: deque = context.chat_data.setdefault("wrong_hist", deque(maxlen=3))
    wrong_streak = context.chat_data.get("wrong_streak", 0)
    context.chat_data["wrong_streak"] = wrong_streak + 1

    if random.random() < 0.1:
        reply = choose_no_recent(LONG_WRONG_REPLIES, wrong_hist, keep_last=3)
    else:
        reply = choose_no_recent(WRONG_REPLIES, wrong_hist, keep_last=3)

    if sarcasm_on() and context.chat_data["wrong_streak"] >= MAX_WRONG_STREAK:
        reply += random.choice([
            "\nЗапишу в личное дело: «решал дела методом тыка».",
            "\nСовет дня: иногда инструкция — друг, а не враг.",
            "\nПопробуй ещё раз. На этот раз — без фристайла."
        ])

    await type_then_reply(update.message, reply)

# ----------------- MAIN -----------------
def main():
    token = os.getenv("BOT_TOKEN", "8302376134:AAFlhYhpEe4tqfrlQvmLhdBK6ryJyCnWrYw")
    app = ApplicationBuilder().token(token).build()

    # Гарантируем наличие JobQueue (на некоторых установках может быть None)
    if app.job_queue is None:
        jq = JobQueue()
        jq.set_application(app)
        jq.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()




