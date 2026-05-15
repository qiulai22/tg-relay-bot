import os
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# 消息映射
message_map = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg:
        return

    # 管理员回复用户
    if msg.chat_id == ADMIN_ID and msg.reply_to_message:
        reply_id = msg.reply_to_message.message_id

        if reply_id in message_map:
            target_user = message_map[reply_id]

            await context.bot.send_message(
                chat_id=target_user,
                text=msg.text
            )
        return

    # 普通用户发来的消息
    user = msg.from_user

    sent = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"来自：{user.full_name}\n"
            f"用户ID：{user.id}\n\n"
            f"{msg.text}"
        )
    )

    # 保存映射
    message_map[sent.message_id] = msg.chat_id

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Bot started")

    app.run_polling()

if __name__ == "__main__":
    main()
