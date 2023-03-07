import html
import json
import os
from typing import Optional

from AstrakoBot import (
    DEV_USERS,
    OWNER_ID,
    SUDO_USERS,
    SUPPORT_CHAT,
    SUPPORT_USERS,
    WHITELIST_USERS,
    dispatcher,
)
from AstrakoBot.modules.helper_funcs.chat_status import (
    dev_plus,
    sudo_plus,
    whitelist_plus,
)
from AstrakoBot.modules.helper_funcs.extraction import extract_user
from AstrakoBot.modules.log_channel import gloggable
from telegram import ParseMode, TelegramError, Update
from telegram.ext import CallbackContext, CommandHandler, run_async
from telegram.utils.helpers import mention_html

ELEVATED_USERS_FILE = os.path.join(os.getcwd(), "AstrakoBot/elevated_users.json")


def check_user_id(user_id: int, context: CallbackContext) -> Optional[str]:
    bot = context.bot
    if not user_id:
        reply = "That...is a chat! baka ka omae?"

    elif user_id == bot.id:
        reply = "This does not work that way."

    else:
        reply = None
    return reply


# This can serve as a deeplink example.
# disasters =
# """ Text here """

# do not async, not a handler
# def send_disasters(update):
#    update.effective_message.reply_text(
#        disasters, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

### Deep link example ends


@dev_plus
@gloggable
def addsudo(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in DEV_USERS:
        message.reply_text("Huh? he is more than sudo!")
        return ""

    if user_id in SUDO_USERS:
        message.reply_text("This user is already sudo")
        return ""

    if user_id in SUPPORT_USERS:
        rt += "Promoted from support user to sudo"
        data["supports"].remove(user_id)
        SUPPORT_USERS.remove(user_id)

    if user_id in WHITELIST_USERS:
        rt += "Promoted from whitelist user to sudo"
        data["whitelists"].remove(user_id)
        WHITELIST_USERS.remove(user_id)

    data["sudos"].append(user_id)
    SUDO_USERS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    update.effective_message.reply_text(
        rt + "\nSuccessfully promoted to sudo!".format(user_member.first_name)
    )

    log_message = (
        f"#SUDO\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@sudo_plus
@gloggable
def addsupport(
    update: Update,
    context: CallbackContext,
) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in DEV_USERS:
        message.reply_text("Huh? he is more than support!")
        return ""

    if user_id in SUDO_USERS:
        if user.id in DEV_USERS:
            rt += "Demoted from sudo to support user"
            data["sudos"].remove(user_id)
            SUDO_USERS.remove(user_id)
        else:
            message.reply_text("This user is already sudo")
            return ""

    if user_id in SUPPORT_USERS:
        message.reply_text("This user is already support")
        return ""

    if user_id in WHITELIST_USERS:
        rt += "Promoted from whitelist to support user"
        data["whitelists"].remove(user_id)
        WHITELIST_USERS.remove(user_id)

    data["supports"].append(user_id)
    SUPPORT_USERS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    update.effective_message.reply_text(
        rt + f"\nSuccessfully promoted {user_member.first_name} to support user"
    )

    log_message = (
        f"#SUPPORT\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@sudo_plus
@gloggable
def addwhitelist(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)
    rt = ""

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in DEV_USERS:
        message.reply_text("Huh? he is more than whitelist!")
        return ""

    if user_id in SUDO_USERS:
        if user.id in DEV_USERS:
            rt += "Demoted from sudo to whitelist user"
            data["sudos"].remove(user_id)
            SUDO_USERS.remove(user_id)
        else:
            message.reply_text("This user is already sudo")
            return ""

    if user_id in SUPPORT_USERS:
        rt += "Demoted from support user to whitelist user"
        data["supports"].remove(user_id)
        SUPPORT_USERS.remove(user_id)

    if user_id in WHITELIST_USERS:
        message.reply_text("This user is already a whitelist user")
        return ""

    data["whitelists"].append(user_id)
    WHITELIST_USERS.append(user_id)

    with open(ELEVATED_USERS_FILE, "w") as outfile:
        json.dump(data, outfile, indent=4)

    update.effective_message.reply_text(
        rt + f"\nSuccessfully promoted {user_member.first_name} to whitelist user!"
    )

    log_message = (
        f"#WHITELIST\n"
        f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))} \n"
        f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
    )

    if chat.type != "private":
        log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

    return log_message


@dev_plus
@gloggable
def removesudo(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in DEV_USERS:
        message.reply_text("Huh? he is more than sudo!")
        return ""

    if user_id in SUDO_USERS:
        message.reply_text("Demoted to normal user")
        SUDO_USERS.remove(user_id)
        data["sudos"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNSUDO\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = "<b>{}:</b>\n".format(html.escape(chat.title)) + log_message

        return log_message

    else:
        message.reply_text("This user is not sudo")
        return ""


@sudo_plus
@gloggable
def removesupport(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in SUPPORT_USERS:
        message.reply_text("Demoted to normal user")
        SUPPORT_USERS.remove(user_id)
        data["supports"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNSUPPORT\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message

    else:
        message.reply_text("This user is not a support user")
        return ""


@sudo_plus
@gloggable
def removewhitelist(update: Update, context: CallbackContext) -> str:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    bot, args = context.bot, context.args
    user_id = extract_user(message, args)
    user_member = bot.getChat(user_id)

    reply = check_user_id(user_id, bot)
    if reply:
        message.reply_text(reply)
        return ""

    with open(ELEVATED_USERS_FILE, "r") as infile:
        data = json.load(infile)

    if user_id in WHITELIST_USERS:
        message.reply_text("Demoting to normal user")
        WHITELIST_USERS.remove(user_id)
        data["whitelists"].remove(user_id)

        with open(ELEVATED_USERS_FILE, "w") as outfile:
            json.dump(data, outfile, indent=4)

        log_message = (
            f"#UNWHITELIST\n"
            f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}\n"
            f"<b>User:</b> {mention_html(user_member.id, html.escape(user_member.first_name))}"
        )

        if chat.type != "private":
            log_message = f"<b>{html.escape(chat.title)}:</b>\n" + log_message

        return log_message
    else:
        message.reply_text("This user is not a whitelist user")
        return ""


@whitelist_plus
def whitelistlist(update: Update, context: CallbackContext):
    bot = context.bot
    message = update.effective_message
    msg = "<b>Whitelist users:</b>\n"
    for each_user in WHITELIST_USERS:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            if user.first_name == "":
                continue
            msg += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    message.reply_text(msg, parse_mode=ParseMode.HTML)


@whitelist_plus
def supportlist(update: Update, context: CallbackContext):
    bot = context.bot
    message = update.effective_message
    msg = "<b>Support users:</b>\n"
    for each_user in SUPPORT_USERS:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            if user.first_name == "":
                continue
            msg += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    message.reply_text(msg, parse_mode=ParseMode.HTML)


@whitelist_plus
def sudolist(update: Update, context: CallbackContext):
    bot = context.bot
    message = update.effective_message
    true_sudo = list(set(SUDO_USERS) - set(DEV_USERS))
    msg = "<b>Sudo users:</b>\n"
    for each_user in true_sudo:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            if user.first_name == "":
                continue
            msg += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    message.reply_text(msg, parse_mode=ParseMode.HTML)


@whitelist_plus
def devlist(update: Update, context: CallbackContext):
    bot = context.bot
    message = update.effective_message
    true_dev = list(set(DEV_USERS) - {OWNER_ID})
    msg = "<b>Developer users:</b>\n"
    for each_user in true_dev:
        user_id = int(each_user)
        try:
            user = bot.get_chat(user_id)
            if user.first_name == "":
                continue
            msg += f"• {mention_html(user_id, html.escape(user.first_name))}\n"
        except TelegramError:
            pass
    message.reply_text(msg, parse_mode=ParseMode.HTML)


__help__ = f"""
*⚠️ Notice:*
Commands listed here only work for users with special access and are mainly used for troubleshooting, debugging purposes.
Group admins/group owners do not need these commands. 

*List all special users:*
• `/sudolist`: lists all users which have sudo access to the bot
• `/supportlist`: lists all users which are allowed to gban, but can also be banned
• `/whitelistlist`: lists all users which cannot be banned, muted flood or kicked but can be manually banned by admins
• `/devlist`: lists all developer users who will have the same perms as the owner
• `/addsudo`: adds a user as sudo
• `/addsupport`: adds a user as support
• `/addwhitelist`: adds a user as whitelist
• `/removesudo`: remove a sudo user
• `/removesupport`: remove support user
• `/removewhitelist`: remove a whitelist user

*Broadcast: (Bot owner only)*
• *Note:* this supports basic markdown
• `/broadcastall`: broadcasts everywhere
• `/broadcastusers`: broadcasts too all users
• `/broadcastgroups`: broadcasts too all groups

*Groups Info:*
• `/groups`: list the groups with Name, ID, members count as a txt
• `/chatlist`: same as groups
• `/leave <ID>`: leave the group, ID must have hyphen
• `/stats`: shows overall bot stats
• `/getchats`: gets a list of group names the user has been seen in. Bot owner only
• `/ginfo username/link/ID`: pulls info panel for entire group

*Access control:* 
• `/ignore`: blacklists a user from using the bot entirely
• `/notice`: removes user from blacklist
• `/ignoredlist`: lists ignored users

*Sys tools:* 
• `/ip`: gets bot connection ip (bot owner only)
• `/ping`: gets ping time of bot to telegram server
• `/speedtest`: runs a speedtest and gives you 2 options to choose from, text or image output
• `/status`: gets some system info

*Global Bans:*
• `/gban <id> <reason>`: gbans the user, works by reply too
• `/ungban`: ungbans the user, same usage as gban
• `/gbanlist`: outputs a list of gbanned users

*Module loading:*
• `/listmodules`: prints modules and their names
• `/unload <name>`: unloads module dynamically
• `/load <name>`: loads module

*Remote commands:*
• `/rban user group`: remote ban
• `/runban user group`: remote un-ban
• `/rpunch user group`: remote punch
• `/rmute user group`: remote mute
• `/runmute user group`: remote un-mute
• `/ginfo username/link/ID`: pulls info panel for entire group

*Chatbot:* 
• `/listaichats`: lists the chats the chatmode is enabled in
 
*Debugging and Shell:* 
• `/debug <on/off>`: logs commands to updates.txt
• `/logs`: run this in support group to get logs in pm
• `/eval`: self explanatory
• `/sh`: runs shell command (bot owner only)
• `/py`: runs python code (bot owner only)
• `/clearlocals`: as the name goes
• `/dbcleanup`: removes deleted accs and groups from db

Visit @{SUPPORT_CHAT} for more information.
"""

SUDO_HANDLER = CommandHandler(("addsudo"), addsudo, run_async=True)
SUPPORT_HANDLER = CommandHandler(("addsupport"), addsupport, run_async=True)
WHITELIST_HANDLER = CommandHandler(("addwhitelist"), addwhitelist, run_async=True)
UNSUDO_HANDLER = CommandHandler(("removesudo"), removesudo, run_async=True)
UNSUPPORT_HANDLER = CommandHandler(("removesupport"), removesupport, run_async=True)
UNWHITELIST_HANDLER = CommandHandler(("removewhitelist"), removewhitelist, run_async=True)

WHITELISTLIST_HANDLER = CommandHandler(("whitelistlist"), whitelistlist, run_async=True)
SUPPORTLIST_HANDLER = CommandHandler(("supportlist"), supportlist, run_async=True)
SUDOLIST_HANDLER = CommandHandler(("sudolist"), sudolist, run_async=True)
DEVLIST_HANDLER = CommandHandler(("devlist"), devlist, run_async=True)

dispatcher.add_handler(SUDO_HANDLER)
dispatcher.add_handler(SUPPORT_HANDLER)
dispatcher.add_handler(WHITELIST_HANDLER)
dispatcher.add_handler(UNSUDO_HANDLER)
dispatcher.add_handler(UNSUPPORT_HANDLER)
dispatcher.add_handler(UNWHITELIST_HANDLER)

dispatcher.add_handler(WHITELISTLIST_HANDLER)
dispatcher.add_handler(SUPPORTLIST_HANDLER)
dispatcher.add_handler(SUDOLIST_HANDLER)
dispatcher.add_handler(DEVLIST_HANDLER)

__mod_name__ = "Super users"
__handlers__ = [
    SUDO_HANDLER,
    SUPPORT_HANDLER,
    WHITELIST_HANDLER,
    UNSUDO_HANDLER,
    UNSUPPORT_HANDLER,
    UNWHITELIST_HANDLER,
    WHITELISTLIST_HANDLER,
    SUPPORTLIST_HANDLER,
    SUDOLIST_HANDLER,
    DEVLIST_HANDLER,
]
