from random import randint

import requests
from AstrakoBot import SUPPORT_CHAT, WALL_API, dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot.modules.helper_funcs.misc import delete
from telegram import Update
from telegram.ext import CallbackContext, run_async

PIXABAY_API = WALL_API

def wall(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    msg = update.effective_message
    args = context.args
    msg_id = update.effective_message.message_id
    bot = context.bot
    query = " ".join(args)
    if not query:
        msg.reply_text("Please enter a query!")
        return
    else:
        caption = query
        term = query.replace(" ", "+")
        response = requests.get(f"https://pixabay.com/api/?key={PIXABAY_API}&q={term}&image_type=photo&per_page=200")

        if response.status_code != 200:
            msg.reply_text(f"An error occurred! Report this @{SUPPORT_CHAT}")
        else:
            data = response.json()
            wallpapers = data.get("hits")
            if not wallpapers:
                msg.reply_text("No results found! Refine your search.")
                return
            else:
                index = randint(0, len(wallpapers) - 1) if len(wallpapers) > 1 else 0
                wallpaper = wallpapers[index].get("largeImageURL")
                wallpaper = wallpaper.replace("\\", "")
                delmsg_preview = bot.send_photo(
                    chat_id,
                    photo=wallpaper,
                    caption="Preview",
                    reply_to_message_id=msg_id,
                    timeout=60,
                )
                delmsg = bot.send_document(
                    chat_id,
                    document=wallpaper,
                    filename="wallpaper",
                    caption=caption,
                    reply_to_message_id=msg_id,
                    timeout=60,
                )

    cleartime = get_clearcmd(chat_id, "wall")

    if cleartime:
        context.dispatcher.run_async(delete, delmsg_preview, cleartime.time)
        context.dispatcher.run_async(delete, delmsg, cleartime.time)


WALLPAPER_HANDLER = DisableAbleCommandHandler("wall", wall, run_async=True)
dispatcher.add_handler(WALLPAPER_HANDLER)
