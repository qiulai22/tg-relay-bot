import os
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
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

# 管理员收到的消息ID -> 用户chat_id
message_map = {}


# =========================
# /test 命令（仅管理员）
# =========================
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text("机器人在线")


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

        # 必须回复消息
        if not msg.reply_to_message:
            await msg.reply_text(
                "请先回复一条机器人转发过来的消息，再发送内容。"
            )
            return

        replied_message_id = msg.reply_to_message.message_id

        target_user = message_map.get(replied_message_id)

        if not target_user:
            await msg.reply_text("找不到对应用户。")
            return

        # =========================
        # 文本
        # =========================
        if msg.text:
            await context.bot.send_message(
                chat_id=target_user,
                text=msg.text
            )

        # =========================
        # 图片
        # =========================
        elif msg.photo:
            await context.bot.send_photo(
                chat_id=target_user,
                photo=msg.photo[-1].file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 视频
        # =========================
        elif msg.video:
            await context.bot.send_video(
                chat_id=target_user,
                video=msg.video.file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 文件
        # =========================
        elif msg.document:
            await context.bot.send_document(
                chat_id=target_user,
                document=msg.document.file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 语音
        # =========================
        elif msg.voice:
            await context.bot.send_voice(
                chat_id=target_user,
                voice=msg.voice.file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 音频
        # =========================
        elif msg.audio:
            await context.bot.send_audio(
                chat_id=target_user,
                audio=msg.audio.file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 动图 GIF
        # =========================
        elif msg.animation:
            await context.bot.send_animation(
                chat_id=target_user,
                animation=msg.animation.file_id,
                caption=msg.caption or ""
            )

        # =========================
        # 贴纸
        # =========================
        elif msg.sticker:
            await context.bot.send_sticker(
                chat_id=target_user,
                sticker=msg.sticker.file_id
            )

        else:
            await msg.reply_text("暂不支持这种消息类型。")
            return

        await msg.reply_text("已发送给用户。")

        return

    # ==================================================
    # 普通用户消息 -> 转发给管理员
    # ==================================================

    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    # 保存映射
    message_map[forwarded.message_id] = msg.chat_id

    # 给用户提示
    await msg.reply_text("已收到，我会转发给管理员。")


# =========================
# 主程序
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # /test
    app.add_handler(CommandHandler("test", test_command))

    # 所有私聊消息
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
