import os
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN 没设置")

if not ADMIN_ID:
    raise Exception("ADMIN_ID 没设置")

ADMIN_ID = int(ADMIN_ID)

message_map = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    print(f"收到消息: chat_id={msg.chat_id}, text={msg.text}")

    # 管理员回复
    if msg.chat_id == ADMIN_ID:
        if not msg.reply_to_message:
            await msg.reply_text("请直接回复机器人转发过来的那条消息。")
            return

        replied_message_id = msg.reply_to_message.message_id
        target_user = message_map.get(replied_message_id)

        if not target_user:
            await msg.reply_text("找不到对应用户。")
            return

        if msg.text:
            await context.bot.send_message(chat_id=target_user, text=msg.text)
            await msg.reply_text("已发送给用户。")
        else:
            await msg.reply_text("目前先支持文字回复。")
        return

    # 普通用户消息 -> 转发给管理员
    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    message_map[forwarded.message_id] = msg.chat_id

    # 给用户一个确认，不然看起来像没反应
    await msg.reply_text("已收到，我会转发给管理员。")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
