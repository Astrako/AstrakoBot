import os
import shutil
import datetime
import subprocess
from time import sleep
from telegram.ext.commandhandler import CommandHandler

from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext

from AstrakoBot import DB_URI, OWNER_ID, dispatcher, LOGGER as log, BACKUP_PASS
from AstrakoBot.modules.helper_funcs.chat_status import owner_plus

@owner_plus
def backup_now(_: Update, ctx: CallbackContext):
    cronjob.run(dispatcher=dispatcher)

@owner_plus
def stop_jobs(update: Update, _: CallbackContext):
    print(j.stop())
    update.effective_message.reply_text("Scheduler has been shut down")

@owner_plus
def start_jobs(update: Update, _: CallbackContext):
    print(j.start())
    update.effective_message.reply_text("Scheduler started")

zip_pass = BACKUP_PASS

def backup_db(_: CallbackContext):
    bot = dispatcher.bot
    tmpmsg = "Performing backup, Please wait..."
    tmp = bot.send_message(OWNER_ID, tmpmsg)
    datenow = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dbbkpname = "db_{}_{}.tar".format(bot.username, datenow)
    bkplocation = "backups/{}".format(datenow)
    bkpcmd = "pg_dump {} --format=tar > {}/{}".format(DB_URI, bkplocation, dbbkpname)

    if not os.path.exists(bkplocation):
        os.makedirs(bkplocation)
    log.info("performing db backup")
    loginfo = "db backup"
    term(bkpcmd, loginfo)
    if not os.path.exists('{}/{}'.format(bkplocation, dbbkpname)):
        bot.send_message(OWNER_ID, "An error occurred during the db backup")
        tmp.edit_text("Backup Failed!")
        sleep(8)
        tmp.delete()
        return 
    else:
        log.info("copying config, and logs to backup location")
        if os.path.exists('logs.txt'):
            print("logs copied")
            shutil.copyfile('logs.txt', '{}/logs.txt'.format(bkplocation))
        if os.path.exists('AstrakoBot/config.py'):
            print("config copied")
            shutil.copyfile('AstrakoBot/config.py', '{}/config.py'.format(bkplocation))
        log.info("zipping the backup")
        zipcmd = "zip --password '{}' {} {}/*".format(zip_pass, bkplocation, bkplocation)
        zipinfo = "zipping db backup"
        log.info("zip started")
        term(zipcmd, zipinfo)
        log.info("zip done")
        sleep(1)
        with open('backups/{}'.format(f'{datenow}.zip'), 'rb') as bkp:
            nm = "{} backup \n".format(bot.username) + datenow
            bot.send_document(OWNER_ID,
                            document=bkp,
                            caption=nm,
                            timeout=20
                            )
        log.info("removing zipped files")
        shutil.rmtree("backups/{}".format(datenow))
        log.info("backup done")
        tmp.edit_text("Backup complete!")
        sleep(5)
        tmp.delete()

@owner_plus
def del_bkp_fldr(update: Update, _: CallbackContext):
    shutil.rmtree("backups")
    update.effective_message.reply_text("'backups' directory has been purged!")

def term(cmd, info):
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    stdout, stderr = process.communicate()
    stderr = stderr.decode()
    stdout = stdout.decode()
    if stdout:
        log.info(f"{info} successful!")
        log.info(f"{stdout}")
    if stderr:
        log.error(f"error while running {info}")
        log.info(f"{stderr}")

from AstrakoBot import updater as u
# run the backup daliy at 1:00
twhen = datetime.datetime.strptime('01:00', '%H:%M').time()
j = u.job_queue
cronjob = j.run_daily(callback=backup_db, name="database backups", time=twhen)

dispatcher.add_handler(CommandHandler("backupdb", backup_now, run_async=True))
dispatcher.add_handler(CommandHandler("stopjobs", stop_jobs, run_async=True))
dispatcher.add_handler(CommandHandler("startjobs", start_jobs, run_async=True))
dispatcher.add_handler(CommandHandler("purgebackups", del_bkp_fldr, run_async=True))