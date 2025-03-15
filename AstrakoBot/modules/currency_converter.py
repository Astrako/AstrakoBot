import requests
from AstrakoBot import CASH_API_KEY, dispatcher
from telegram import Update, ParseMode
from telegram.ext import CallbackContext, CommandHandler, run_async
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot.modules.helper_funcs.misc import delete

def convert(update: Update, context: CallbackContext):
    chat = update.effective_chat
    args = update.effective_message.text.split(" ")

    if len(args) == 4:
        try:
            orig_cur_amount = float(args[1])
        except ValueError:
            update.effective_message.reply_text("Invalid amount of currency")
            return

        orig_cur = args[2].upper()
        new_cur = args[3].upper()
        api_version = "v6"
        data = None

        try:
            request_url = f"https://v6.exchangerate-api.com/v6/{CASH_API_KEY}/latest/{orig_cur}"
            response = requests.get(request_url)
            data = response.json()

            if data.get('result') == 'error':
                api_version = "v4"
                request_url = f"https://api.exchangerate-api.com/v4/latest/{orig_cur}"
                response = requests.get(request_url)
                data = response.json()

        except Exception as e:
            update.effective_message.reply_text(f"API Error: {str(e)}")
            return

        if not data or 'result' in data and data['result'] == 'error':
            error_key = 'error_type' if api_version == "v4" else 'error-type'
            error_msg = data.get(error_key, 'Unknown API error') if data else 'Empty API response'
            update.effective_message.reply_text(f"Error: {error_msg}")
            return

        if api_version == "v6":
            if not data.get('conversion_rates'):
                update.effective_message.reply_text("Invalid API response format")
                return
            rates = data['conversion_rates']
        else:
            if not data.get('rates'):
                update.effective_message.reply_text("Invalid API response format")
                return
            rates = data['rates']

        if new_cur not in rates:
            update.effective_message.reply_text(f"Currency {new_cur} is not supported.")
            return

        current_rate = rates[new_cur]
        new_cur_amount = round(orig_cur_amount * current_rate, 5)
        delmsg = update.effective_message.reply_text(
            f"{orig_cur_amount} {orig_cur} = {new_cur_amount} {new_cur}"
        )

    elif len(args) == 1:
        delmsg = update.effective_message.reply_text("Check extras module help for `/cash` usage", parse_mode=ParseMode.MARKDOWN)

    else:
        delmsg = update.effective_message.reply_text(
            f"*Invalid Arguments!* Required 3 parameters but got {len(args)-1}",
            parse_mode=ParseMode.MARKDOWN,
        )

    cleartime = get_clearcmd(chat.id, "cash")
    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)

CONVERTER_HANDLER = CommandHandler("cash", convert, run_async=True)
dispatcher.add_handler(CONVERTER_HANDLER)
