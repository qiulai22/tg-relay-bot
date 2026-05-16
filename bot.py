import os
import time
import sqlite3
import re
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# =========================
# 环境变量
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN 没设置")

if not ADMIN_ID_RAW:
    raise Exception("ADMIN_ID 没设置")

ADMIN_ID = int(ADMIN_ID_RAW.strip())

# =========================
# SQLite
# =========================
DB_PATH = "messages.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # 管理员消息ID -> 用户chat_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_map (
                admin_message_id INTEGER PRIMARY KEY,
                user_chat_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        # 已处理的用户消息，防止重复转发
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
        """)

        # 配置项
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # 默认配置
        cursor.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            ("rate_limit_seconds", "3")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            ("history_days", "7")
        )

        conn.commit()

def save_mapping(admin_message_id: int, user_chat_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO message_map (admin_message_id, user_chat_id, created_at) VALUES (?, ?, ?)",
            (admin_message_id, user_chat_id, int(time.time()))
        )
        conn.commit()

def get_mapping(admin_message_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_chat_id FROM message_map WHERE admin_message_id = ?",
            (admin_message_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

def is_processed(chat_id: int, message_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_messages WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id)
        )
        return cursor.fetchone() is not None

def mark_processed(chat_id: int, message_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO processed_messages (chat_id, message_id, created_at) VALUES (?, ?, ?)",
            (chat_id, message_id, int(time.time()))
        )
        conn.commit()

def clear_history():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM message_map")
        cursor.execute("DELETE FROM processed_messages")
        conn.commit()

def get_config_int(key: str, default: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return default
        try:
            return int(row[0])
        except ValueError:
            return default

def set_config_int(key: str, value: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()

def cleanup_old_messages():
    history_days = get_config_int("history_days", 7)
    expire_time = int(time.time()) - (history_days * 24 * 60 * 60)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM message_map WHERE created_at < ?",
            (expire_time,)
        )
        cursor.execute(
            "DELETE FROM processed_messages WHERE created_at < ?",
            (expire_time,)
        )
        conn.commit()

# 启动时初始化并清理一次
init_db()
cleanup_old_messages()

# =========================
# 防刷屏
# =========================
rate_limit_cache = {}
RATE_LIMIT_SECONDS = get_config_int("rate_limit_seconds", 3)

# =========================
# 管理员交互状态
# =========================
# None / "setratelimit" / "sethistorydays"
pending_admin_action = None

def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)

def should_rate_limit(chat_id: int) -> bool:
    now = time.time()
    last_time = rate_limit_cache.get(chat_id, 0)

    if now - last_time < RATE_LIMIT_SECONDS:
        return True

    rate_limit_cache[chat_id] = now
    return False

def is_pure_digits(text: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+", text.strip()))

# =========================
# /test
# =========================
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("机器人在线")

# =========================
# /status
# =========================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    cleanup_old_messages()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM message_map")
        total_map = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processed_messages")
        total_processed = cursor.fetchone()[0]

    pending_text = "无"
    if pending_admin_action == "setratelimit":
        pending_text = "等待设置防刷屏时间"
    elif pending_admin_action == "sethistorydays":
        pending_text = "等待设置历史保留天数"

    text = (
        "机器人状态正常\n\n"
        f"管理员ID: {ADMIN_ID}\n"
        f"已保存消息映射: {total_map}\n"
        f"已记录去重消息: {total_processed}\n"
        f"防刷屏间隔: {RATE_LIMIT_SECONDS} 秒\n"
        f"历史保留: {get_config_int('history_days', 7)} 天\n"
        f"当前等待输入: {pending_text}"
    )
    await update.message.reply_text(text)

# =========================
# /clearhistory
# =========================
async def clear_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    clear_history()
    rate_limit_cache.clear()
    await update.message.reply_text("历史消息记录已清空。")

# =========================
# /setratelimit
# 先发命令，再发下一条消息作为数字
# =========================
async def set_ratelimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_admin_action

    if not is_admin(update):
        return

    pending_admin_action = "setratelimit"
    await update.message.reply_text("请发送要设置的防刷屏时间（纯数字，单位：秒）。")

# =========================
# /sethistorydays
# 先发命令，再发下一条消息作为数字
# =========================
async def set_history_days_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_admin_action

    if not is_admin(update):
        return

    pending_admin_action = "sethistorydays"
    await update.message.reply_text("请发送要设置的历史保留天数（纯数字）。")

# =========================
# 主消息处理
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_admin_action
    global RATE_LIMIT_SECONDS

    msg = update.message
    if not msg:
        return

    cleanup_old_messages()

    # =========================
    # 管理员消息
    # =========================
    if msg.chat_id == ADMIN_ID:

        # 先处理“等待设置参数”的情况
        if pending_admin_action in ("setratelimit", "sethistorydays"):
            if not msg.text:
                await msg.reply_text("请发送纯数字。")
                return

            value_text = msg.text.strip()

            if not is_pure_digits(value_text):
                await msg.reply_text("输入必须是纯数字，不能包含文字、字母或符号。")
                return

            value = int(value_text)

            if pending_admin_action == "setratelimit":
                if value > 3600:
                    await msg.reply_text("防刷屏时间过大，建议不要超过 3600 秒。")
                    return

                RATE_LIMIT_SECONDS = value
                set_config_int("rate_limit_seconds", value)
                rate_limit_cache.clear()
                pending_admin_action = None
                await msg.reply_text(f"防刷屏时间已设置为 {value} 秒。")
                return

            if pending_admin_action == "sethistorydays":
                if value < 1:
                    await msg.reply_text("保留天数不能小于 1。")
                    return

                if value > 365:
                    await msg.reply_text("保留天数过大，建议不要超过 365。")
                    return

                set_config_int("history_days", value)
                cleanup_old_messages()
                pending_admin_action = None
                await msg.reply_text(f"历史保留天数已设置为 {value} 天。")
                return

        # 正常管理员回复用户
        if not msg.reply_to_message:
            await msg.reply_text("请先回复一条机器人转发过来的消息，再发送内容。")
            return

        replied_message_id = msg.reply_to_message.message_id
        target_user = get_mapping(replied_message_id)

        if not target_user:
            await msg.reply_text(
                "找不到对应用户。可能是消息过旧、机器人重启过，或者这条不是机器人转发的消息。"
            )
            return

        try:
            # 文本
            if msg.text:
                await context.bot.send_message(
                    chat_id=target_user,
                    text=msg.text
                )

            # 图片
            elif msg.photo:
                await context.bot.send_photo(
                    chat_id=target_user,
                    photo=msg.photo[-1].file_id,
                    caption=msg.caption or ""
                )

            # 视频
            elif msg.video:
                await context.bot.send_video(
                    chat_id=target_user,
                    video=msg.video.file_id,
                    caption=msg.caption or ""
                )

            # 文件
            elif msg.document:
                await context.bot.send_document(
                    chat_id=target_user,
                    document=msg.document.file_id,
                    caption=msg.caption or ""
                )

            # 语音
            elif msg.voice:
                await context.bot.send_voice(
                    chat_id=target_user,
                    voice=msg.voice.file_id
                )

            # 音频
            elif msg.audio:
                await context.bot.send_audio(
                    chat_id=target_user,
                    audio=msg.audio.file_id,
                    caption=msg.caption or ""
                )

            # GIF
            elif msg.animation:
                await context.bot.send_animation(
                    chat_id=target_user,
                    animation=msg.animation.file_id,
                    caption=msg.caption or ""
                )

            # 贴纸
            elif msg.sticker:
                await context.bot.send_sticker(
                    chat_id=target_user,
                    sticker=msg.sticker.file_id
                )

            else:
                await msg.reply_text("暂不支持这种消息类型。")
                return

            await msg.reply_text("已发送给用户。")

        except Exception:
            await msg.reply_text("发送失败。")

        return

    # =========================
    # 普通用户消息
    # =========================
    if should_rate_limit(msg.chat_id):
        await msg.reply_text("发送太快了，请稍后再试。")
        return

    # 去重：同一用户同一条消息只记录一次
    if is_processed(msg.chat_id, msg.message_id):
        return

    try:
        forwarded = await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id
        )

        save_mapping(forwarded.message_id, msg.chat_id)
        mark_processed(msg.chat_id, msg.message_id)

        await msg.reply_text("已收到，我会转发给管理员。")

    except Exception:
        await msg.reply_text("消息发送失败，请稍后重试。")

# =========================
# 主程序
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clearhistory", clear_history_command))
    app.add_handler(CommandHandler("setratelimit", set_ratelimit_command))
    app.add_handler(CommandHandler("sethistorydays", set_history_days_command))

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_message
        )
    )

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
