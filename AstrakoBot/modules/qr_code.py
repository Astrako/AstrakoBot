import requests
from AstrakoBot import dispatcher
from telegram import Update, ParseMode
from telegram.ext import CallbackContext, CommandHandler, run_async
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot.modules.helper_funcs.misc import delete
from datetime import datetime

from urllib.parse import quote
from telegram import Update
from telegram.ext import CallbackContext
import requests
from io import BytesIO

def qr_encode(update: Update, context: CallbackContext):
    message = update.effective_message
    data = None

    if message.reply_to_message:
        replied_msg = message.reply_to_message
        data = replied_msg.caption or replied_msg.text
        if not data:
            message.reply_text("Replied message has no text/caption!")
            return
    else:
        if not context.args:
            message.reply_text("Please provide text or reply to a message!\nExample: /qr_encode hello world")
            return
        data = ' '.join(context.args)

    try:
        encoded_data = quote(data)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?data={encoded_data}"

        response = requests.get(qr_url)
        response.raise_for_status()

        img_file = BytesIO(response.content)
        img_file.name = "qrcode.png"

        message.reply_document(
            document=img_file,
            filename="qrcode.png"
        )

    except requests.exceptions.RequestException as e:
        message.reply_text(f"Failed to generate QR code: {str(e)}")
    except Exception as e:
        message.reply_text(f"An error occurred: {str(e)}")

def qr_decode(update: Update, context: CallbackContext):
    message = update.effective_message
    target = message.reply_to_message or message

    photo = target.photo[-1] if target.photo else None
    document = target.document

    file = None
    file_size = 0
    if photo:
        file_size = photo.file_size
        file = photo.get_file()
    elif document and document.mime_type.startswith('image/'):
        file_size = document.file_size
        file = document.get_file()
    else:
        message.reply_text("Please reply to or send an image containing a QR code")
        return

    if file_size > 1048576:
        message.reply_text("Image too large! Max 1MB allowed")
        return

    try:
        img_data = BytesIO()
        file.download(out=img_data)
        img_data.seek(0)

        response = requests.post(
            'https://api.qrserver.com/v1/read-qr-code/',
            files={'file': ('qrcode', img_data, 'application/octet-stream')}
        )
        response.raise_for_status()
        result = response.json()

        if result and isinstance(result, list):
            symbol_list = result[0].get('symbol', [{}])
            if not symbol_list:
                return message.reply_text("No QR symbol data found")
            text = symbol_list[0].get('data')
            if text:
                allowed_controls = {'\t', '\n', '\r'}
                if all(c.isprintable() or c in allowed_controls for c in text):
                    return message.reply_text(f"Decoded QR content:\n\n{text}")
                else:
                    return message.reply_text("QR Code contains unprintable characters")
            else:
                return message.reply_text("QR Code contains no readable data")
        else:
            return message.reply_text("Invalid or empty QR Code response")

    except requests.exceptions.RequestException as e:
        message.reply_text(f"API Error: {str(e)}")
    except Exception as e:
        message.reply_text(f"Decoding failed: {str(e)}")

__help__ = """
*Available commands:*\n
*QR Code:*
• `/qr`, `/qr_encode`: Encode text to QR Code\n
• `/qr_decode`: Decode QR Code to text\n
"""

ENCODE_HANDLER = CommandHandler(["qr", "qr_encode"], qr_encode, run_async=True)
DECODE_HANDLER = CommandHandler("qr_decode", qr_decode, run_async=True)

dispatcher.add_handler(ENCODE_HANDLER)
dispatcher.add_handler(DECODE_HANDLER)

__mod_name__ = "QR Code"
__command_list__ = ["qr", "qr_encode", "qr_decode"]
__handlers__ = [ENCODE_HANDLER, DECODE_HANDLER]
