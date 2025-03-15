import requests
from AstrakoBot import dispatcher
from telegram import Update, ParseMode
from telegram.ext import CallbackContext, CommandHandler, run_async
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot.modules.helper_funcs.misc import delete
from datetime import datetime
import re

def linux_kernels(update: Update, context: CallbackContext):
    chat = update.effective_chat
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0"}

    try:
        response = requests.get("https://www.kernel.org/releases.json", headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        update.effective_message.reply_text(f"Error fetching kernel data: {str(e)}")
        return

    releases = data.get("releases", [])
    if not releases:
        update.effective_message.reply_text("No kernel releases found.")
        return

    message = "<b>Linux Kernel Versions</b>\n\n"
    for release in releases[:10]:
        version = release.get("version", "Unknown")
        moniker = release.get("moniker", "").lower()
        timestamp = release.get("released", {}).get("timestamp", 0)
        source_url = release.get("gitweb", "#")

        category = "MAINLINE"
        if release.get("iseol"):
            category = "EOL"
        elif "longterm" in moniker:
            category = "LTS"
        elif "stable" in moniker:
            category = "STABLE"
        elif "linux-next" in moniker:
            category = "NEXT"

        message += (
            f"• <a href='{source_url}'>{version}</a>\n"
            f"  └ <i>{category}</i> "
            f"({datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')})\n\n"
        )

    message += "<i>Source: kernel.org</i>"

    try:
        delmsg = update.effective_message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        update.effective_message.reply_text(f"Error formatting message: {str(e)}")
        return

    cleartime = get_clearcmd(chat.id, "kernels")
    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)

__help__ = """
*Available commands:*\n
*Linux Kernel:*
• `/kernels`: fetches linux kernels information\n
"""

KERNELS_HANDLER = CommandHandler("kernels", linux_kernels, run_async=True)
dispatcher.add_handler(KERNELS_HANDLER)

__mod_name__ = "Linux"
__command_list__ = ["kernels"]
__handlers__ = [KERNELS_HANDLER]
