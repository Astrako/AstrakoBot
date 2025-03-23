import wikipedia, os, glob
from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from AstrakoBot.modules.helper_funcs.misc import delete
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, run_async
from wikipedia.exceptions import DisambiguationError, PageError


def wiki(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat
    msg = ""
    definition = message.text[len("/wiki ") :]
    if definition:
        res = ""
        search = message.text
        try:
            res = wikipedia.summary(search)
        except DisambiguationError:
            msg = 'Disambiguated pages found! Adjust your query accordingly'
        except PageError:
            msg = 'An error happened getting the wiki page, try again with other term'
        if res:
            msg = f"*{search}*\n\n"
            msg += f"`{res}`\n\n"
            msg += f"Read more: https://en.wikipedia.org/wiki/{definition}"
            if len(msg) > 4000:
                with open("result.txt", "w") as f:
                    f.write(f"{res}\n\nUwU OwO OmO UmU")
                with open("result.txt", "rb") as f:
                    delmsg = context.bot.send_document(
                        document=f,
                        filename=f.name,
                        reply_to_message_id=update.message.message_id,
                        chat_id=update.effective_chat.id,
                        parse_mode=ParseMode.HTML,
                    )

                    try:
                        for f in glob.glob("result.txt"):
                            os.remove(f)
                    except Exception:
                        pass

    else:
        msg = 'Give me something to get from Wikipedia, like:\n`/wiki Madrid`'

    delmsg = message.reply_text(
        text = msg,
        parse_mode = ParseMode.MARKDOWN,
        disable_web_page_preview = True,
    )

    cleartime = get_clearcmd(chat.id, "wiki")

    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)



WIKI_HANDLER = DisableAbleCommandHandler("wiki", wiki, run_async=True)
dispatcher.add_handler(WIKI_HANDLER)
