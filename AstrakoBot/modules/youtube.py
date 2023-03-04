import os
import json
import random
import string
from datetime import datetime
from telegram import Bot, Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext, run_async
from AstrakoBot.modules.sql.clear_cmd_sql import get_clearcmd
from AstrakoBot import dispatcher
from AstrakoBot.modules.disable import DisableAbleCommandHandler
from AstrakoBot.modules.helper_funcs.misc import delete
import pytube
from moviepy.editor import *

def get_random():
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(10))

def is_ytl(url):
    return 'youtube.com/watch?v=' in url or 'youtu.be/' in url

def format_link(youtube_link):
    if "youtu.be/" in youtube_link:
        youtube_link = youtube_link.replace('youtu.be/', 'youtube.com/watch?v=')
    if '&ab_channel' in youtube_link:
        youtube_link = youtube_link.split('&ab_channel')[0]
    return youtube_link

def dyt_video(youtube_link, resolution, filename):
    youtube_link = format_link(youtube_link)
    youtube = pytube.YouTube(youtube_link)

    # Try to get video length at least 5 times
    for i in range(5):
        try:
            video_length = youtube.length / 60
            break
        except:
            if i == 4:
                return "Could not get video length! Try again in a few seconds or try another video."


    if video_length > 10: # 10 minutes limit for video
        return "Video is longer than 10 minutes! Try again with a shorter one."

    video_streams = youtube.streams
    available_resolutions = [stream.resolution for stream in video_streams if stream.resolution is not None]
    if resolution not in available_resolutions:
        resolution = max(available_resolutions, key=lambda x: int(x[:-1]))

    video_stream = youtube.streams.filter(resolution=resolution, progressive=True).order_by('resolution').desc().first()
    audio_stream = youtube.streams.filter(only_audio=True).order_by('abr').desc().first()

    video_file = video_stream.download(filename="{}.mp4".format(get_random()))
    audio_file = audio_stream.download(filename="{}.mp3".format(get_random()))

    video_clip = VideoFileClip(video_file)
    audio_clip = AudioFileClip(audio_file)
    final_clip = video_clip.set_audio(audio_clip)
    final_clip.write_videofile(filename, codec='libx264', audio_codec='aac')

    try:
        os.remove(video_file)
        os.remove(audio_file)
    except:
        pass

    return ""

def dyt_audio(youtube_link, filename):
    youtube_link = format_link(youtube_link)
    youtube = YouTube(youtube_link)

    # Try to get video length at least 5 times, even with this, pytube may fail sometimes.
    for i in range(5):
        try:
            video_length = youtube.length / 60
            break
        except:
            if i == 5:
                return "Could not get video length! Try again in a few seconds or try another video."

    if video_length > 30: # 30 minutes limit for audio
        return "Audio is longer than 30 minutes! Try again with a shorter one."

    audio_stream = youtube.streams.filter(only_audio=True, abr="128kbps").first()

    try:
        audio_stream.download(filename=filename)
    except:
        return "Unknown Error."
    return ""

def youtube(update: Update, context: CallbackContext):
    message_id = update.message.message_id
    message = update.effective_message
    chat = update.effective_chat
    args = context.args
    chat_id = update.effective_chat.id
    if not args or not is_ytl(args[0]):
        message.reply_text("Specify a song or video!")
        return
    yt = args[0]
    avail_res = ["720p", "480p", "360p", "240p", "144p"] # Limit to HD due to file size
    types = ["video", "audio"]
    type = "video"
    res = avail_res[0]
    for i in types:
        if i in args:
            type = i
            break
    for i in avail_res:
        if i in args or i[:-1] in args:
            res = i
            if not res.endswith("p"):
                res += "p"
            break

    filename = get_random()

    if type == "video":
        filename += ".mp4"
        msg = message.reply_text("Downloading as video, Please wait...")
        ret = dyt_video(yt, res, filename)
        caption = "Type: mp4\nQuality: {}".format(res)
        if ret == "":
            msg.edit_text("Uploading...")
            with open(filename, "rb") as video:
                context.bot.send_video(chat_id=chat_id, video=video, caption=caption, reply_to_message_id=message_id)
            msg.delete()
        else:
            msg.edit_text(ret)

    else:
        filename += ".mp3"
        msg = message.reply_text("Downloading as mp3 audio, Please wait...")
        ret = dyt_video(yt, res, filename)
        caption = "Type: mp3\nQuality: 128kbps".format(res)
        if ret == "":
            msg.edit_text("Uploading...")
            with open(filename, "rb") as audio:
                context.bot.send_audio(chat_id=chat_id, audio=audio, caption=caption.format(type), reply_to_message_id=message_id)
            msg.delete()
        else:
            msg.edit_text(ret)

    try:
        os.remove(filename)
    except Exception:
        pass

    return

YOUTUBE_HANDLER = DisableAbleCommandHandler(["youtube", "yt"], youtube, run_async = True)
dispatcher.add_handler(YOUTUBE_HANDLER)
