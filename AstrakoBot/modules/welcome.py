import html
import random
import re
import time
from functools import partial
from contextlib import suppress

import AstrakoBot.modules.sql.welcome_sql as sql
import AstrakoBot
from AstrakoBot import (
    DEV_USERS,
    LOGGER,
    OWNER_ID,
    SUDO_USERS,
    SUPPORT_USERS,
    WHITELIST_USERS,
    sw,
    dispatcher,
    JOIN_LOGGER,
)
from AstrakoBot.modules.helper_funcs.chat_status import (
    is_user_ban_protected,
    user_admin,
)
from AstrakoBot.modules.helper_funcs.misc import build_keyboard, delete, revert_buttons
from AstrakoBot.modules.helper_funcs.msg_types import get_welcome_type
from AstrakoBot.modules.helper_funcs.string_handling import (
    escape_invalid_curly_brackets,
    markdown_parser,
)
from AstrakoBot.modules.log_channel import loggable
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot.modules.sql.global_bans_sql import is_user_gbanned
from AstrakoBot.modules.helper_funcs.admin_status import get_bot_member
from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    run_async, ChatMemberHandler,
)
from telegram.utils.helpers import escape_markdown, mention_html, mention_markdown

VALID_WELCOME_FORMATTERS = [
    "first",
    "last",
    "fullname",
    "username",
    "id",
    "count",
    "chatname",
    "mention",
]

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video,
}

VERIFIED_USER_WAITLIST = {}


# do not async
def send(update, message, keyboard, backup_message, reply_to_message=None):
    if not message:
        return

    chat = update.effective_chat
    try:
        msg = dispatcher.bot.send_message(chat.id,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=True,
            allow_sending_without_reply=True,
        )
    except TypeError:
        msg = dispatcher.bot.send_message(chat.id,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            allow_sending_without_reply=True,
        )
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            msg = dispatcher.bot.send_message(chat.id,
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                quote=False,
                disable_web_page_preview=True,
                allow_sending_without_reply=True,
            )
        elif excp.message == "Button_url_invalid":
            msg = dispatcher.bot.send_message(chat.id,
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has an invalid url "
                    "in one of its buttons. Please update.",
                ),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                allow_sending_without_reply=True,
            )
        elif excp.message == "Unsupported url protocol":
            msg = dispatcher.bot.send_message(chat.id,
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has buttons which "
                    "use url protocols that are unsupported by "
                    "telegram. Please update.",
                ),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                allow_sending_without_reply=True,
            )
        elif excp.message == "Wrong url host":
            msg = dispatcher.bot.send_message(chat.id,
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has some bad urls. "
                    "Please update.",
                ),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                allow_sending_without_reply=True,
            )
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Could not parse! got invalid url host errors")
        elif excp.message == "Have no rights to send a message":
            return
        else:
            msg = dispatcher.bot.send_message(chat.id,
                markdown_parser(
                    backup_message +
                    "\nNote: An error occured when sending the "
                    "custom message. Please update.",
                ),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                allow_sending_without_reply=True,
            )
            LOGGER.exception(
                "An error occured when sending a custom message to %s",
                chat.id,
            )
    return msg


def welcomeFilter(update: Update, context: CallbackContext):
    if update.effective_chat.type != "group" and update.effective_chat.type != "supergroup":
        return
    if nm := update.chat_member.new_chat_member:
        om = update.chat_member.old_chat_member
        if nm.status == nm.MEMBER and (om.status == nm.KICKED or om.status == nm.LEFT):
            return new_member(update, context)
        if (nm.status == nm.KICKED or nm.status == nm.LEFT) and \
                (om.status == nm.MEMBER or om.status == nm.ADMINISTRATOR or om.status == nm.CREATOR):
            return left_member(update, context)

@loggable
def new_member(update: Update, context: CallbackContext):
    bot, job_queue = context.bot, context.job_queue
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    should_welc, cust_welcome, cust_content, welc_type = sql.get_welc_pref(chat.id)
    welc_mutes = sql.welcome_mutes(chat.id)
    human_checks = sql.get_human_checks(user.id, chat.id)
    new_mem = update.chat_member.new_chat_member.user

    if new_mem.id == bot.id and not AstrakoBot.ALLOW_CHATS:
        with suppress(BadRequest):
            dispatcher.bot.send_message(chat.id, f"Groups are disabled for {bot.first_name}, I'm outta here.")
        bot.leave_chat(update.effective_chat.id)
        return

    welcome_log = None
    res = None
    sent = None
    should_mute = True
    welcome_bool = True
    media_wel = False
    keyboard = None
    backup_message = ""
    reply = None


    if sw is not None:
        sw_ban = sw.get_ban(new_mem.id)
        if sw_ban:
            return

    if is_user_gbanned(new_mem.id):
        return

    if should_welc:

        # Give the owner a special welcome
        if new_mem.id == OWNER_ID:
            deletion(update, context, dispatcher.bot.send_message(chat.id,
                "Oh, Genos? Let's get this moving."
            ))
            welcome_log = (
                f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"Bot Owner just joined the group"
            )

        # Welcome Devs
        elif new_mem.id in DEV_USERS:
            deletion(update, context, dispatcher.bot.send_message(chat.id,
                "Whoa! A developer user just joined!",
            ))
            welcome_log = (
                f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"Bot Dev just joined the group"
            )

        # Welcome Sudos
        elif new_mem.id in SUDO_USERS:
            deletion(update, context, dispatcher.bot.send_message(chat.id,
                "Huh! A sudo user just joined! Stay Alert!",
            ))
            welcome_log = (
                f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"Bot Sudo just joined the group"
            )

        # Welcome Support
        elif new_mem.id in SUPPORT_USERS:
            deletion(update, context, dispatcher.bot.send_message(chat.id,
                "Huh! A support user just joined!",
            ))
            welcome_log = (
                f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"Bot Support just joined the group"
            )

        # Welcome Whitelisted
        elif new_mem.id in WHITELIST_USERS:
            deletion(update, context, dispatcher.bot.send_message(chat.id,
                "Oof! A whitelist user just joined!",
            ))
            welcome_log = (
                f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"Bot whitelisted just joined the group"
            )

        # Welcome yourself
        elif new_mem.id == bot.id:
            dispatcher.bot.send_message(chat.id,
                "Thanks for adding me! Join https://t.me/AstrakoBotSupport for support.",
                disable_web_page_preview=True,
            )

            bot.send_message(
                JOIN_LOGGER,
                "#NEW_GROUP\n<b>Group name:</b> {}\n<b>ID:</b> <code>{}</code>".format(
                    html.escape(chat.title), chat.id
                ),
                parse_mode=ParseMode.HTML,
            )
        else:
            buttons = sql.get_welc_buttons(chat.id)
            keyb = build_keyboard(buttons)

            if welc_type not in (sql.Types.TEXT, sql.Types.BUTTON_TEXT):
                media_wel = True

            first_name = (
                new_mem.first_name or "PersonWithNoName"
            )  # edge case of empty name - occurs for some bugs.

            if cust_welcome:
                if cust_welcome == sql.DEFAULT_WELCOME:
                    cust_welcome = random.choice(
                        sql.DEFAULT_WELCOME_MESSAGES
                    ).format(first=escape_markdown(first_name))

                if new_mem.last_name:
                    fullname = escape_markdown(f"{first_name} {new_mem.last_name}")
                else:
                    fullname = escape_markdown(first_name)
                count = chat.get_member_count()
                mention = mention_markdown(new_mem.id, escape_markdown(first_name))
                if new_mem.username:
                    username = "@" + escape_markdown(new_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(
                    cust_welcome, VALID_WELCOME_FORMATTERS
                )
                res = valid_format.format(
                    first=escape_markdown(first_name),
                    last=escape_markdown(new_mem.last_name or first_name),
                    fullname=escape_markdown(fullname),
                    username=username,
                    mention=mention,
                    count=count,
                    chatname=escape_markdown(chat.title),
                    id=new_mem.id,
                )

            else:
                res = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(
                    first=escape_markdown(first_name)
                )
                keyb = []

            backup_message = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(
                first=escape_markdown(first_name)
            )
            keyboard = InlineKeyboardMarkup(keyb)
    else:
        welcome_bool = False
        backup_message = None

    # User exceptions from welcomemutes
    if (
        is_user_ban_protected(chat, new_mem.id, chat.get_member(new_mem.id))
        or human_checks
    ):
        should_mute = False
    # Join welcome: soft mute
    if new_mem.is_bot:
        should_mute = False

    if user.id == new_mem.id:
        if should_mute:
            if welc_mutes == "soft":
                bot.restrict_chat_member(
                    chat.id,
                    new_mem.id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=False,
                        can_send_other_messages=False,
                        can_invite_users=False,
                        can_pin_messages=False,
                        can_send_polls=False,
                        can_change_info=False,
                        can_add_web_page_previews=False,
                    ),
                    until_date=(int(time.time() + 24 * 60 * 60)),
                )
            if welc_mutes == "strong":
                welcome_bool = False
                if not media_wel:
                    VERIFIED_USER_WAITLIST.update(
                        {
                            new_mem.id: {
                                "should_welc": should_welc,
                                "media_wel": False,
                                "status": False,
                                "update": update,
                                "res": res,
                                "keyboard": keyboard,
                                "backup_message": backup_message,
                            }
                        }
                    )
                else:
                    VERIFIED_USER_WAITLIST.update(
                        {
                            new_mem.id: {
                                "should_welc": should_welc,
                                "chat_id": chat.id,
                                "status": False,
                                "media_wel": True,
                                "cust_content": cust_content,
                                "welc_type": welc_type,
                                "res": res,
                                "keyboard": keyboard,
                            }
                        }
                    )
                new_join_mem = f'<a href="tg://user?id={user.id}">{html.escape(new_mem.first_name)}</a>'
                message = dispatcher.bot.send_message(chat.id,
                    f"{new_join_mem}, click the button below to prove you're human.\nYou have 60 seconds.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            {
                                InlineKeyboardButton(
                                    text="Yes, I'm human.",
                                    callback_data=f"user_join_({new_mem.id})",
                                )
                            }
                        ]
                    ),
                    parse_mode=ParseMode.HTML,
                )
                if get_bot_member(chat.id).can_restrict_members:
                    bot.restrict_chat_member(
                        chat.id,
                        new_mem.id,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_invite_users=False,
                            can_pin_messages=False,
                            can_send_polls=False,
                            can_change_info=False,
                            can_send_media_messages=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False,
                        ),
                    )
                job_queue.run_once(
                    partial(check_not_bot, new_mem, chat.id, message.message_id),
                    60,
                    name="welcomemute",
                )

    if welcome_bool:
        if media_wel:
            # Stickers have no caption, send separately
            if welc_type == sql.Types.STICKER:
                sent = ENUM_FUNC_MAP[welc_type](
                    chat.id,
                    cust_content,
                    reply_markup=keyboard
                ) and ENUM_FUNC_MAP[sql.Types.TEXT](
                    chat.id,
                    res,
                    parse_mode="markdown"
                )
            else:
                sent = ENUM_FUNC_MAP[welc_type](
                    chat.id,
                    cust_content,
                    caption=res,
                    reply_markup=keyboard,
                    parse_mode="markdown"
                )
        else:
            sent = send(update, res, keyboard, backup_message)
        deletion(update, context, sent)
        prev_welc = sql.get_clean_pref(chat.id)
        if prev_welc:
            try:
                bot.delete_message(chat.id, prev_welc)
            except BadRequest:
                pass

            if sent:
                sql.set_clean_welcome(chat.id, sent.message_id)

    if welcome_log:
        return welcome_log

    if user.id == new_mem.id:
        welcome_log = (
            f"{html.escape(chat.title)}\n"
            f"#USER_JOINED\n"
            f"<b>User</b>: {mention_html(user.id, user.first_name)}\n"
            f"<b>ID</b>: <code>{user.id}</code>"
        )
    elif new_mem.is_bot and user.id != new_mem.id:
        welcome_log = (
            f"{html.escape(chat.title)}\n"
            f"#BOT_ADDED\n"
            f"<b>Bot</b>: {mention_html(new_mem.id, new_mem.first_name)}\n"
            f"<b>ID</b>: <code>{new_mem.id}</code>"
        )
    else:
        welcome_log = (
            f"{html.escape(chat.title)}\n"
            f"#USER_ADDED\n"
            f"<b>User</b>: {mention_html(new_mem.id, new_mem.first_name)}\n"
            f"<b>ID</b>: <code>{new_mem.id}</code>"
        )
    return welcome_log



def check_not_bot(member, chat_id, message_id, context):
    bot = context.bot
    member_dict = VERIFIED_USER_WAITLIST.pop(member.id)
    member_status = member_dict.get("status")
    if not member_status:
        try:
            bot.unban_chat_member(chat_id, member.id)
        except:
            pass

        try:
            bot.edit_message_text(
                "*Kicks user*\nThey can always rejoin and try.",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode = ParseMode.MARKDOWN,
            )
        except:
            pass


def cleanServiceFilter(u: Update, _):
    if u.effective_message.left_chat_member or u.effective_message.new_chat_members:
        return handleCleanService(u)


def handleCleanService(update: Update):
    if sql.clean_service(update.effective_chat.id):
        try:
            dispatcher.bot.delete_message(update.effective_chat.id, update.message.message_id)
        except BadRequest:
            pass


def left_member(update: Update, context: CallbackContext):
    bot = context.bot
    chat = update.effective_chat
    user = update.effective_user
    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)

    if user.id == bot.id:
        return

    if should_goodbye:

        left_mem = update.chat_member.new_chat_member.user
        if left_mem:

            # Thingy for spamwatched users
            if sw is not None:
                sw_ban = sw.get_ban(left_mem.id)
                if sw_ban:
                    return

            # Dont say goodbyes to gbanned users
            if is_user_gbanned(left_mem.id):
                return

            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                dispatcher.bot.send_message(chat.id,
                    "Oi! Genos! He left..",
                )
                return

            # Give the devs a special goodbye
            elif left_mem.id in DEV_USERS:
                dispatcher.bot.send_message(chat.id,
                    "See you later dev!",
                )
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                ENUM_FUNC_MAP[goodbye_type](chat.id, cust_goodbye)
                return

            first_name = (
                left_mem.first_name or "PersonWithNoName"
            )  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if cust_goodbye == sql.DEFAULT_GOODBYE:
                    cust_goodbye = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(
                        first=escape_markdown(first_name)
                    )
                if left_mem.last_name:
                    fullname = escape_markdown(f"{first_name} {left_mem.last_name}")
                else:
                    fullname = escape_markdown(first_name)
                count = chat.get_member_count()
                mention = mention_markdown(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape_markdown(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(
                    cust_goodbye, VALID_WELCOME_FORMATTERS
                )
                res = valid_format.format(
                    first=escape_markdown(first_name),
                    last=escape_markdown(left_mem.last_name or first_name),
                    fullname=escape_markdown(fullname),
                    username=username,
                    mention=mention,
                    count=count,
                    chatname=escape_markdown(chat.title),
                    id=left_mem.id,
                )
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(
                    first=first_name
                )
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            delmsg = send(
                update,
                res,
                keyboard,
                random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(first=first_name),
            )

            deletion(update, context, delmsg)


@user_admin
def welcome(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    # if no args, show current replies.
    if not args or args[0].lower() == "noformat":
        noformat = bool(args and args[0].lower() == "noformat")
        pref, welcome_m, cust_content, welcome_type = sql.get_welc_pref(chat.id)
        update.effective_message.reply_text(
            f"This chat has it's welcome setting set to: `{pref}`.\n"
            f"*The welcome message (not filling the {{}}) is:*",
            parse_mode=ParseMode.MARKDOWN,
        )

        if welcome_type in [sql.Types.BUTTON_TEXT, sql.Types.TEXT]:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)
        else:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                ENUM_FUNC_MAP[welcome_type](chat.id, cust_content, caption=welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)
                ENUM_FUNC_MAP[welcome_type](
                    chat.id,
                    cust_content,
                    caption=welcome_m,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text(
                "Okay! I'll greet members when they join."
            )

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text(
                "I'll go loaf around and not welcome anyone then."
            )

        else:
            update.effective_message.reply_text(
                "I understand 'on/yes' or 'off/no' only!"
            )


@user_admin
def goodbye(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat

    if not args or args[0] == "noformat":
        noformat = bool(args and args[0].lower() == "noformat")
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        update.effective_message.reply_text(
            f"This chat has it's goodbye setting set to: `{pref}`.\n"
            f"*The goodbye  message (not filling the {{}}) is:*",
            parse_mode=ParseMode.MARKDOWN,
        )

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        elif noformat:
            ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m)

        else:
            ENUM_FUNC_MAP[goodbye_type](
                chat.id, goodbye_m, parse_mode=ParseMode.MARKDOWN
            )

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            update.effective_message.reply_text("Ok!")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text("Ok!")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text(
                "I understand 'on/yes' or 'off/no' only!"
            )


@user_admin
@loggable
def set_welcome(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_welcome(chat.id, content, text, data_type, buttons)
    msg.reply_text("Successfully set custom welcome message!")

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#SET_WELCOME\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Set the welcome message."
    )


@user_admin
@loggable
def reset_welcome(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_welcome(chat.id, None, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text(
        "Successfully reset welcome message to default!"
    )

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#RESET_WELCOME\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Reset the welcome message to default."
    )


@user_admin
@loggable
def set_goodbye(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_gdbye(chat.id, content or text, data_type, buttons)
    msg.reply_text("Successfully set custom goodbye message!")
    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#SET_GOODBYE\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Set the goodbye message."
    )


@user_admin
@loggable
def reset_goodbye(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text(
        "Successfully reset goodbye message to default!"
    )

    return (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#RESET_GOODBYE\n"
        f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
        f"Reset the goodbye message."
    )


@user_admin
@loggable
def welcomemute(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if len(args) >= 1:
        if args[0].lower() in ("off", "no"):
            sql.set_welcome_mutes(chat.id, False)
            msg.reply_text("I will no longer mute people on joining!")
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>OFF</b>."
            )
        elif args[0].lower() in ["soft"]:
            sql.set_welcome_mutes(chat.id, "soft")
            msg.reply_text(
                "I will restrict users' permission to send media for 24 hours."
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>SOFT</b>."
            )
        elif args[0].lower() in ["strong"]:
            sql.set_welcome_mutes(chat.id, "strong")
            msg.reply_text(
                "I will now mute people when they join until they prove they're not a bot.\nThey will have 60 seconds before they get kicked."
            )
            return (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#WELCOME_MUTE\n"
                f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled welcome mute to <b>STRONG</b>."
            )
        else:
            msg.reply_text(
                "Please enter <code>off</code>/<code>no</code>/<code>soft</code>/<code>strong</code>!",
                parse_mode=ParseMode.HTML,
            )
            return ""
    else:
        curr_setting = sql.welcome_mutes(chat.id)
        reply = (
            f"\n Give me a setting!\nChoose one out of: <code>off</code>/<code>no</code> or <code>soft</code> or <code>strong</code> only! \n"
            f"Current setting: <code>{curr_setting}</code>"
        )
        msg.reply_text(reply, parse_mode=ParseMode.HTML)
        return ""


@user_admin
@loggable
def clean_welcome(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            update.effective_message.reply_text(
                "I should be deleting welcome messages up to two days old."
            )
        else:
            update.effective_message.reply_text(
                "I'm currently not deleting old welcome messages!"
            )
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_clean_welcome(str(chat.id), True)
        update.effective_message.reply_text("I'll try to delete old welcome messages!")
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#CLEAN_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Has toggled clean welcomes to <code>ON</code>."
        )
    elif args[0].lower() in ("off", "no"):
        sql.set_clean_welcome(str(chat.id), False)
        update.effective_message.reply_text("I won't delete old welcome messages.")
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#CLEAN_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Has toggled clean welcomes to <code>OFF</code>."
        )
    else:
        update.effective_message.reply_text("I understand 'on/yes' or 'off/no' only!")
        return ""


@user_admin
def cleanservice(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type != chat.PRIVATE:
        if len(args) >= 1:
            var = args[0]
            if var in ("no", "off"):
                sql.set_clean_service(chat.id, False)
                update.effective_message.reply_text("Welcome clean service is : off")
            elif var in ("yes", "on"):
                sql.set_clean_service(chat.id, True)
                update.effective_message.reply_text("Welcome clean service is : on")
            else:
                update.effective_message.reply_text(
                    "Invalid option", parse_mode=ParseMode.HTML
                )
        else:
            update.effective_message.reply_text(
                "Usage is <code>on</code>/<code>yes</code> or <code>off</code>/<code>no</code>",
                parse_mode=ParseMode.HTML,
            )
    else:
        curr = sql.clean_service(chat.id)
        if curr:
            update.effective_message.reply_text(
                "Welcome clean service is : <code>on</code>", parse_mode=ParseMode.HTML
            )
        else:
            update.effective_message.reply_text(
                "Welcome clean service is : <code>off</code>", parse_mode=ParseMode.HTML
            )


def user_button(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    query = update.callback_query
    bot = context.bot
    match = re.match(r"user_join_\((.+?)\)", query.data)
    message = update.effective_message
    join_user = int(match.group(1))

    if join_user == user.id:
        sql.set_human_checks(user.id, chat.id)
        member_dict = VERIFIED_USER_WAITLIST.pop(user.id)
        member_dict["status"] = True
        VERIFIED_USER_WAITLIST.update({user.id: member_dict})
        query.answer(text="Yeet! You're a human, unmuted!")
        if get_bot_member(chat.id).can_restrict_members:
            bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                    can_send_polls=True,
                    can_change_info=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
        try:
            bot.deleteMessage(chat.id, message.message_id)
        except:
            pass
        if member_dict["should_welc"] and welc_type:
            if member_dict["media_wel"]:
                if welc_type == sql.Types.STICKER:
                    sent = ENUM_FUNC_MAP[member_dict["welc_type"]](
                        member_dict["chat_id"],
                        member_dict["cust_content"],
                        reply_markup=member_dict["keyboard"],
                    ) and ENUM_FUNC_MAP[sql.Types.TEXT](
                        member_dict["chat_id"],
                        member_dict["res"],
                        parse_mode="markdown",
                    )
                else:
                    sent = ENUM_FUNC_MAP[member_dict["welc_type"]](
                        member_dict["chat_id"],
                        member_dict["cust_content"],
                        caption=member_dict["res"],
                        reply_markup=member_dict["keyboard"],
                        parse_mode="markdown",
                    )
            else:
                sent = send(
                    member_dict["update"],
                    member_dict["res"],
                    member_dict["keyboard"],
                    member_dict["backup_message"],
                )

            prev_welc = sql.get_clean_pref(chat.id)
            if prev_welc:
                try:
                    bot.delete_message(chat.id, prev_welc)
                except BadRequest:
                    pass

                if sent:
                    sql.set_clean_welcome(chat.id, sent.message_id)

    else:
        query.answer(text="You're not allowed to do this!")


WELC_HELP_TXT = (
    "Your group's welcome/goodbye messages can be personalised in multiple ways. If you want the messages"
    " to be individually generated, like the default welcome message is, you can use *these* variables:\n"
    " • `{first}`*:* this represents the user's *first* name\n"
    " • `{last}`*:* this represents the user's *last* name. Defaults to *first name* if user has no "
    "last name.\n"
    " • `{fullname}`*:* this represents the user's *full* name. Defaults to *first name* if user has no "
    "last name.\n"
    " • `{username}`*:* this represents the user's *username*. Defaults to a *mention* of the user's "
    "first name if has no username.\n"
    " • `{mention}`*:* this simply *mentions* a user - tagging them with their first name.\n"
    " • `{id}`*:* this represents the user's *id*\n"
    " • `{count}`*:* this represents the user's *member number*.\n"
    " • `{chatname}`*:* this represents the *current chat name*.\n"
    "\nEach variable MUST be surrounded by `{}` to be replaced.\n"
    "Welcome messages also support markdown, so you can make any elements bold/italic/code/links. "
    "Buttons are also supported, so you can make your welcomes look awesome with some nice intro "
    "buttons.\n"
    f"To create a button linking to your rules, use this: `[Rules](buttonurl://t.me/{dispatcher.bot.username}?start=group_id)`. "
    "Simply replace `group_id` with your group's id, which can be obtained via /id, and you're good to "
    "go. Note that group ids are usually preceded by a `-` sign; this is required, so please don't "
    "remove it.\n"
    "You can even set images/gifs/videos/voice messages as the welcome message by "
    "replying to the desired media, and calling `/setwelcome`."
)

WELC_MUTE_HELP_TXT = (
    "You can get the bot to mute new people who join your group and hence prevent spambots from flooding your group. "
    "The following options are possible:\n"
    "• `/welcomemute soft`*:* restricts new members from sending media for 24 hours.\n"
    "• `/welcomemute strong`*:* mutes new members till they tap on a button thereby verifying they're human.\n"
    "• `/welcomemute off`*:* turns off welcomemute.\n"
    "*Note:* Strong mode kicks a user from the chat if they dont verify in 60 seconds. They can always rejoin though"
)


@user_admin
def welcome_help(update: Update, context: CallbackContext):
    update.effective_message.reply_text(WELC_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


@user_admin
def welcome_mute_help(update: Update, context: CallbackContext):
    update.effective_message.reply_text(
        WELC_MUTE_HELP_TXT, parse_mode=ParseMode.MARKDOWN
    )


def deletion(update: Update, context: CallbackContext, delmsg):
    chat = update.effective_chat
    cleartime = get_clearcmd(chat.id, "welcome")

    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)


# TODO: get welcome data from group butler snap
# def __import_data__(chat_id, data):
#     welcome = data.get('info', {}).get('rules')
#     welcome = welcome.replace('$username', '{username}')
#     welcome = welcome.replace('$name', '{fullname}')
#     welcome = welcome.replace('$id', '{id}')
#     welcome = welcome.replace('$title', '{chatname}')
#     welcome = welcome.replace('$surname', '{lastname}')
#     welcome = welcome.replace('$rules', '{rules}')
#     sql.set_custom_welcome(chat_id, welcome, sql.Types.TEXT)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    welcome_pref = sql.get_welc_pref(chat_id)[0]
    goodbye_pref = sql.get_gdbye_pref(chat_id)[0]
    return (
        "This chat has it's welcome preference set to `{}`.\n"
        "It's goodbye preference is `{}`.".format(welcome_pref, goodbye_pref)
    )


__help__ = """
*Admins only:*
 • `/welcome <on/off>`*:* enable/disable welcome messages.
 • `/welcome`*:* shows current welcome settings.
 • `/welcome noformat`*:* shows current welcome settings, without the formatting - useful to recycle your welcome messages!
 • `/goodbye`*:* same usage and args as `/welcome`.
 • `/setwelcome <sometext>`*:* set a custom welcome message. If used replying to media, uses that media.
 • `/setgoodbye <sometext>`*:* set a custom goodbye message. If used replying to media, uses that media.
 • `/resetwelcome`*:* reset to the default welcome message.
 • `/resetgoodbye`*:* reset to the default goodbye message.
 • `/cleanwelcome <on/off>`*:* On new member, try to delete the previous welcome message to avoid spamming the chat.
 • `/welcomemutehelp`*:* gives information about welcome mutes.
 • `/cleanservice <on/off`*:* deletes telegrams welcome/left service messages. 
 *Example:*
user joined chat, user left chat.

*Welcome markdown:* 
 • `/welcomehelp`*:* view more formatting information for custom welcome/goodbye messages.
"""

dispatcher.add_handler(
    ChatMemberHandler(
        welcomeFilter, ChatMemberHandler.CHAT_MEMBER, run_async=True
    ), group=-100)

dispatcher.add_handler(
    MessageHandler(Filters.chat_type.groups, cleanServiceFilter), group=100)


WELC_PREF_HANDLER = CommandHandler("welcome", welcome, filters=Filters.chat_type.groups, run_async=True)
GOODBYE_PREF_HANDLER = CommandHandler("goodbye", goodbye, filters=Filters.chat_type.groups, run_async=True)
SET_WELCOME = CommandHandler("setwelcome", set_welcome, filters=Filters.chat_type.groups, run_async=True)
SET_GOODBYE = CommandHandler("setgoodbye", set_goodbye, filters=Filters.chat_type.groups, run_async=True)
RESET_WELCOME = CommandHandler("resetwelcome", reset_welcome, filters=Filters.chat_type.groups, run_async=True)
RESET_GOODBYE = CommandHandler("resetgoodbye", reset_goodbye, filters=Filters.chat_type.groups, run_async=True)
WELCOMEMUTE_HANDLER = CommandHandler("welcomemute", welcomemute, filters=Filters.chat_type.groups, run_async=True)
CLEAN_SERVICE_HANDLER = CommandHandler(
    "cleanservice", cleanservice, filters=Filters.chat_type.groups, run_async=True
)
CLEAN_WELCOME = CommandHandler("cleanwelcome", clean_welcome, filters=Filters.chat_type.groups, run_async=True)
WELCOME_HELP = CommandHandler("welcomehelp", welcome_help, run_async=True)
WELCOME_MUTE_HELP = CommandHandler("welcomemutehelp", welcome_mute_help, run_async=True)
BUTTON_VERIFY_HANDLER = CallbackQueryHandler(user_button, pattern=r"user_join_", run_async=True)

dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(CLEAN_WELCOME)
dispatcher.add_handler(WELCOME_HELP)
dispatcher.add_handler(WELCOMEMUTE_HANDLER)
dispatcher.add_handler(CLEAN_SERVICE_HANDLER)
dispatcher.add_handler(BUTTON_VERIFY_HANDLER)
dispatcher.add_handler(WELCOME_MUTE_HELP)

__mod_name__ = "Welcomes/Goodbyes"
__command_list__ = []
__handlers__ = [
    WELC_PREF_HANDLER,
    GOODBYE_PREF_HANDLER,
    SET_WELCOME,
    SET_GOODBYE,
    RESET_WELCOME,
    RESET_GOODBYE,
    CLEAN_WELCOME,
    WELCOME_HELP,
    WELCOMEMUTE_HANDLER,
    CLEAN_SERVICE_HANDLER,
    BUTTON_VERIFY_HANDLER,
    WELCOME_MUTE_HELP,
]
