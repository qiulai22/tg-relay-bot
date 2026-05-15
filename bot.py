import os
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN 没设置")

if not ADMIN_ID:
    raise Exception("ADMIN_ID 没设置")

ADMIN_ID = int(ADMIN_ID)

# 管理员消息ID -> 用户chat_id
message_map = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg:
        return

    # =========================
    # 管理员回复用户
    # =========================
    if msg.chat_id == ADMIN_ID:

        # 必须回复消息
        if not msg.reply_to_message:
            return

        replied_message_id = msg.reply_to_message.message_id

        target_user = message_map.get(replied_message_id)

        if not target_user:
            await msg.reply_text("找不到对应用户")
            return

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

        # 文件
        elif msg.document:
            await context.bot.send_document(
                chat_id=target_user,
                document=msg.document.file_id,
                caption=msg.caption or ""
            )

        # 视频
        elif msg.video:
            await context.bot.send_video(
                chat_id=target_user,
                video=msg.video.file_id,
                caption=msg.caption or ""
            )

        # 语音
        elif msg.voice:
            await context.bot.send_voice(
                chat_id=target_user,
                voice=msg.voice.file_id,
                caption=msg.caption or ""
            )

        return

    # =========================
    # 普通用户消息 -> 转发给管理员
    # =========================

    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    # 保存映射
    message_map[forwarded.message_id] = msg.chat_id


def main():
    app = Application.builder().token(BOT_TOKEN).build()

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
