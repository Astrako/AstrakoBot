from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from telegram import Update
from telegram.ext import CallbackContext, run_async


def shout(update: Update, context: CallbackContext):
    args = context.args
    message = update.effective_message

    text = ""
    if args:
        text = " ".join(args)
    elif message.reply_to_message:
        text = message.reply_to_message.caption or message.reply_to_message.text or ""

    if not text:
        message.reply_text("What should i shout?")
        return

    result = []
    result.append(" ".join([s for s in text]))
    for pos, symbol in enumerate(text[1:]):
        result.append(symbol + " " + "  " * pos + symbol)
    result = list("\n".join(result))
    result[0] = text[0]
    result = "".join(result)
    msg = "```\n" + result + "```"
    return message.reply_text(msg, parse_mode="MARKDOWN")


SHOUT_HANDLER = DisableAbleCommandHandler("shout", shout, run_async=True)

dispatcher.add_handler(SHOUT_HANDLER)

__command_list__ = ["shout"]
__handlers__ = [SHOUT_HANDLER]
