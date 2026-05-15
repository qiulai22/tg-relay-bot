import os
import time
import sqlite3
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
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN 没设置")

if not ADMIN_ID:
    raise Exception("ADMIN_ID 没设置")

ADMIN_ID = int(ADMIN_ID)

# =========================
# SQLite
# =========================
DB_PATH = "messages.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_map (
                admin_message_id INTEGER PRIMARY KEY,
                user_chat_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
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

def cleanup_old_messages():
    expire_time = int(time.time()) - (7 * 24 * 60 * 60)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM message_map WHERE created_at < ?",
            (expire_time,)
        )
        conn.commit()

# 启动时清理一次
init_db()
cleanup_old_messages()

# =========================
# 防刷屏
# =========================
rate_limit = {}
RATE_LIMIT_SECONDS = 3

# =========================
# /test
# =========================
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text("机器人在线")

# =========================
# /status
# =========================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    if update.effective_user.id != ADMIN_ID:
        return

    cleanup_old_messages()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM message_map")
        total = cursor.fetchone()[0]

    text = (
        "机器人状态正常\n\n"
        f"管理员ID: {ADMIN_ID}\n"
        f"已保存消息映射: {total}\n"
        f"防刷屏间隔: {RATE_LIMIT_SECONDS} 秒"
    )
    await update.message.reply_text(text)

# =========================
# 主消息处理
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # ==================================================
    # 管理员消息
    # ==================================================
    if msg.chat_id == ADMIN_ID:

        # 管理员必须回复机器人转发过来的消息
        if not msg.reply_to_message:
            await msg.reply_text("请先回复一条机器人转发过来的消息，再发送内容。")
            return

        replied_message_id = msg.reply_to_message.message_id
        target_user = get_mapping(replied_message_id)

        if not target_user:
            await msg.reply_text("找不到对应用户。可能是消息过旧、机器人重启过，或者这条不是机器人转发的消息。")
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

    # ==================================================
    # 普通用户消息
    # ==================================================
    now = time.time()
    last_time = rate_limit.get(msg.chat_id, 0)

    if now - last_time < RATE_LIMIT_SECONDS:
        await msg.reply_text("发送太快了，请稍后再试。")
        return

    rate_limit[msg.chat_id] = now

    try:
        forwarded = await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id
        )

        save_mapping(forwarded.message_id, msg.chat_id)

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
