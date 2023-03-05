import requests
from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from AstrakoBot.modules.helper_funcs.misc import delete
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, run_async
import re

def ud(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat
    text = message.text[len("/ud ") :]
    results = requests.get(
        f"https://api.urbandictionary.com/v0/define?term={text}"
    ).json()
    try:
        reply_text = f'*{text}*\n\n{results["list"][0]["definition"]}\n\n_{results["list"][0]["example"]}_'
    except:
        reply_text = "No results found."
    try:
        delmsg = message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
    except:
        reply_text = re.sub(r'\*(.*?)\*', r'\1', reply_text)
        plain_text = reply_text.split('\n')
        for i in range(1, len(plain_text)):
            plain_text[i] = plain_text[i].replace('_', '')
        plain_text = '\n'.join(plain_text)
        delmsg = message.reply_text(plain_text)

    cleartime = get_clearcmd(chat.id, "ud")

    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)


UD_HANDLER = DisableAbleCommandHandler(["ud"], ud, run_async=True)

dispatcher.add_handler(UD_HANDLER)

__command_list__ = ["ud"]
__handlers__ = [UD_HANDLER]
