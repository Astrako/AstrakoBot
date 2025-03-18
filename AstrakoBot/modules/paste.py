import requests
from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, run_async

def paste(update: Update, context: CallbackContext):
    args = context.args
    message = update.effective_message

    if message.reply_to_message:
        data = message.reply_to_message.text

    elif len(args) >= 1:
        data = message.text.split(None, 1)[1]

    else:
        message.reply_text("What am I supposed to do with this?")
        return

    reply_text = "Dpaste failed!"
    try:
        response = requests.post(
            "https://dpaste.com/api/v2/",
            data={
                "content": data,
                "syntax": "text",
                "expiry_days": 7
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        response.raise_for_status()
        url = response.text.strip()
        reply_text = f"Dpasted: {url}"
    except Exception as e:
        reply_text = f"Dpaste failed: {e}"

    message.reply_text(
        reply_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


PASTE_HANDLER = DisableAbleCommandHandler("paste", paste, run_async=True)
dispatcher.add_handler(PASTE_HANDLER)

__command_list__ = ["paste"]
__handlers__ = [PASTE_HANDLER]
