from telegram import ParseMode, Update
from telegram.ext import CallbackContext, run_async
import requests
import urllib.parse

from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from AstrakoBot.modules.helper_funcs.misc import delete
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd

languages = {
    "af": "Afrikaans",
    "sq": "Albanian",
    "am": "Amharic",
    "ar": "Arabic",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "eu": "Basque",
    "be": "Belarusian",
    "bn": "Bengali",
    "bs": "Bosnian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "ceb": "Cebuano",
    "ny": "Chichewa",
    "zh-cn": "Chinese",
    "co": "Corsican",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "eo": "Esperanto",
    "et": "Estonian",
    "tl": "Filipino",
    "fi": "Finnish",
    "fr": "French",
    "fy": "Frisian",
    "gl": "Galician",
    "ka": "Georgian",
    "de": "German",
    "el": "Greek",
    "gu": "Gujarati",
    "ht": "Haitian Creole",
    "ha": "Hausa",
    "haw": "Hawaiian",
    "iw": "Hebrew",
    "hi": "Hindi",
    "hmn": "Hmong",
    "hu": "Hungarian",
    "is": "Icelandic",
    "ig": "Igbo",
    "id": "Indonesian",
    "ga": "Irish",
    "it": "Italian",
    "ja": "Japanese",
    "jw": "Javanese",
    "kn": "Kannada",
    "kk": "Kazakh",
    "km": "Khmer",
    "rw": "Kinyarwanda",
    "ko": "Korean",
    "ku": "Kurdish",
    "ky": "Kyrgyz",
    "lo": "Lao",
    "la": "Latin",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "lb": "Luxembourgish",
    "mk": "Macedonian",
    "mg": "Malagasy",
    "ms": "Malay",
    "ml": "Malayalam",
    "mt": "Maltese",
    "mi": "Maori",
    "mr": "Marathi",
    "mn": "Mongolian",
    "my": "Myanmar",
    "ne": "Nepali",
    "no": "Norwegian",
    "or": "Odia",
    "ps": "Pashto",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "pa": "Punjabi",
    "ro": "Romanian",
    "ru": "Russian",
    "sm": "Samoan",
    "gd": "Scots Gaelic",
    "sr": "Serbian",
    "st": "Sesotho",
    "sn": "Shona",
    "sd": "Sindhi",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "es": "Spanish",
    "su": "Sundanese",
    "sw": "Swahili",
    "sv": "Swedish",
    "tg": "Tajik",
    "ta": "Tamil",
    "tt": "Tatar",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "tk": "Turkmen",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "ug": "Uyghur",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "cy": "Welsh",
    "xh": "Xhosa",
    "yi": "Yiddish",
    "yo": "Yoruba",
    "zu": "Zulu"
}


def tr(text, srcLang, targetLang):
    text = urllib.parse.quote_plus(text)

    # Try to get response at least 3 times
    for _ in range(3):
        try:
            response = requests.get("https://translate.googleapis.com/translate_a/single?client=gtx&sl={}&tl={}&dt=t&q={}".format(srcLang, targetLang, text), timeout=4)
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            pass
    else:
        return ""

    if response.status_code != 200:
        return ""
    data = response.json()
    translated_text = ""
    for item in data[0]:
        translated_text += item[0]
    return translated_text

def totranslate(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    reply = message.reply_to_message
    text = ""
    if reply:
        if reply.document or reply.video or reply.animation or reply.photo:
            if reply.caption:
                text = reply.caption
        elif reply.text:
            text = reply.text

    if text == "":
        delmsg = message.reply_text(
            "Reply to messages from other languages for translating into the intended language\n\n"
            "Example: `/tr en-ml` to translate from English to Malayalam\n"
            "Or use: `/tr ml` for automatic detection and translating it into Malayalam.\n"
            "See [List of Language Codes](t.me/OnePunchSupport/12823) for a list of language codes.",
            parse_mode="markdown",
            disable_web_page_preview=True,
        )
        deletion(update, context, delmsg)
        return
    if not args:
        srcLang = "auto"
        targetLang = "en" # Default to english if no arguments were given
    elif "-" in args[0]:
        try:
            srcLang = args[0].split('-')[0]
        except:
            srcLang = "auto"
        try:
            targetLang = args[0].split('-')[1]
        except:
            message.reply_text("Well damn, that does not look like a target language")
            return
    else:
        try:
            srcLang = args[0]
            targetLang = args[1]
        except:
            targetLang = args[0]
            srcLang = "auto"

    # Convert them to lowercase so we don't get issues
    srcLang = srcLang.lower()
    targetLang = targetLang.lower()


    # If target language is 'english', set it to 'en'
    for key, value in languages.items():
        if value.lower() == targetLang:
            targetLang = key
            break

    # If source language is 'english', set it to 'en'
    for key, value in languages.items():
        if value.lower() == srcLang:
            srcLang = key
            break

    # Make sure language actually exists
    if targetLang not in languages:
        message.reply_text("That does not look like a valid language.")
        return

    reply_msg = message.reply_text("Translating to {}...".format(languages[targetLang]))
    translated = tr(text, srcLang, targetLang)
    if translated == "":
        reply_msg.edit_text("Failed to translate to {}. Try again in a few seconds or try another target language!".format(languages[targetLang]))
        return
    reply_msg.edit_text("Translated to {}:\n\n".format(languages[targetLang]) + translated)
    return


def deletion(update: Update, context: CallbackContext, delmsg):
    chat = update.effective_chat
    cleartime = get_clearcmd(chat.id, "tr")

    if cleartime:
        context.dispatcher.run_async(delete, delmsg, cleartime.time)


__help__ = """
• `/tr` or `/tl` (language code) as reply to a long message
*Example:* 
  `/tr en`*:* translates something to english
  `/tr hi-en`*:* translates hindi to english
"""

TRANSLATE_HANDLER = DisableAbleCommandHandler(["tr", "tl"], totranslate, run_async=True)

dispatcher.add_handler(TRANSLATE_HANDLER)

__mod_name__ = "Translator"
__command_list__ = ["tr", "tl"]
__handlers__ = [TRANSLATE_HANDLER]
