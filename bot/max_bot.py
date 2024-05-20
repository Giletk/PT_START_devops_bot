import logging
import re
import paramiko
import os
import psycopg2
import subprocess

from psycopg2 import Error
from dotenv import load_dotenv
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

load_dotenv()

token = os.getenv('TOKEN')

RM_HOST = os.getenv('RM_HOST')
RM_PORT = os.getenv('RM_PORT')
RM_USER = os.getenv('RM_USER')
RM_PASSWORD = os.getenv('RM_PASSWORD')

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

DB_REPL_USER = os.getenv('DB_REPL_USER')
DB_REPL_PASSWORD = os.getenv('DB_REPL_PASSWORD')
DB_REPL_HOST = os.getenv('DB_REPL_HOST')
DB_REPL_PORT = os.getenv('DB_REPL_PORT')
DB_DATABASE = os.getenv('DB_DATABASE')

# Подключаем логирование
logging.basicConfig(
    filename='logfile.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO, encoding="utf-8"
)

logger = logging.getLogger(__name__)

# Инициализируем нужные функции
def start(update: Update, context):
    user = update.effective_user
    update.message.reply_text(f'Привет, {user.full_name}!')

def helpCommand(update: Update, context):
    update.message.reply_text('Help!')

def findEmailsCommand(update: Update, context):
    update.message.reply_text('Введите текст для поиска email-адресов: ')
    return 'findEmails'

def findPhoneNumbersCommand(update: Update, context):
    update.message.reply_text('Введите текст для поиска телефонных номеров: ')
    return 'findPhoneNumbers'

def verifyPasswordCommand(update: Update, context):
    update.message.reply_text('Введите пароль для проверки сложности: ')
    return 'verifyPassword'

def findEmails(update: Update, context):
    user_input = update.message.text
    emailRegex = re.compile(
        r'(?<!\S)(?:[A-Za-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.(?!$)[A-Za-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|'
        r'"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@'
        r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}'
    )
    emailList = emailRegex.findall(user_input)

    if not emailList:
        update.message.reply_text('Email-адреса не найдены')
        return ConversationHandler.END

    emails = ''
    for i, email in enumerate(emailList):
        emails += f'{i+1}. {email}\n'

    update.message.reply_text(emails)

    update.message.reply_text('Хотите сохранить найденные email-адреса в базе данных? (да/нет)')
    context.user_data['emails'] = emailList
    return 'saveEmails'

def findPhoneNumbers(update: Update, context):
    user_input = update.message.text
    phoneNumRegex = re.compile(r'((?:\+7|8)[- ]?(?:\(\d{3}\)|\d{3})[- ]?\d{3}[- ]?\d{2}[- ]?\d{2})\b')
    phoneNumberList = phoneNumRegex.findall(user_input)

    if not phoneNumberList:
        update.message.reply_text('Телефонные номера не найдены')
        return ConversationHandler.END

    phoneNumbers = ''
    for i, phoneNumber in enumerate(phoneNumberList):
        phoneNumbers += f'{i+1}. {phoneNumber}\n'
    update.message.reply_text(phoneNumbers)

    update.message.reply_text('Хотите сохранить найденные номера телефонов в базе данных? (да/нет)')
    context.user_data['phone_numbers'] = phoneNumberList

    return 'savePhoneNumbers'

def saveEmails(update: Update, context):
    user_response = update.message.text.lower()
    emailList = context.user_data.get('emails', [])

    if user_response == 'да':
        for email in enumerate(emailList):
            db("INSERT INTO email_table (email) VALUES ('" + str(email[1]) + "');", DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE, 'insert')

        update.message.reply_text('Email-адреса успешно сохранены в базе данных')
    else:
        update.message.reply_text('Email-адреса не будут сохранены в базе данных')

    return ConversationHandler.END

def savePhoneNumbers(update: Update, context):
    user_response = update.message.text.lower()
    phoneNumberList = context.user_data.get('phone_numbers', [])

    if user_response == 'да':
        for phoneNumber in enumerate(phoneNumberList):
            db("INSERT INTO phone_table (phone_number) VALUES ('" + str(phoneNumber[1]) + "');", DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE, 'insert')

        update.message.reply_text('Номера телефонов успешно сохранены в базе данных')
    else:
        update.message.reply_text('Номера телефонов не будут сохранены в базе данных')

    return ConversationHandler.END

def verifyPassword(update: Update, context):
    user_input = update.message.text
    passwordRegex = re.compile(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$')
    if passwordRegex.match(user_input):
        update.message.reply_text('Пароль сложный')
    else:
        update.message.reply_text('Пароль простой')
    return ConversationHandler.END

def get_app_list_all(update: Update, context):
    update.message.reply_text(linux('dpkg -l | head -n 11', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))
    return ConversationHandler.END

def get_app_list_one(update: Update, context):
    update.message.reply_text('Введите название пакета для поиска информации: ')
    return 'get_app_info'

def get_app_info(update: Update, context):
    package_name = update.message.text.strip()
    app_info = linux(f'dpkg -s {package_name}', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT)
    update.message.reply_text(app_info)
    return ConversationHandler.END

def get_app_list_command(update: Update, context):
    update.message.reply_text('Введите 1, если хотите видеть информацию о первых 10 установленных пакетах; введите 2, если хотите видеть информацию о конкретном пакете: ')
    return 'get_app_list_choice'

def get_app_list_choice(update: Update, context):
    user_input = update.message.text
    if user_input == '1':
        return get_app_list_all(update, context)
    elif user_input == '2':
        return get_app_list_one(update, context)
    update.message.reply_text('Неверный ввод')
    return ConversationHandler.END

def echo(update: Update, context):
    update.message.reply_text(update.message.text)

def linux(command: str, host: str, username: str, password: str, port: str):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, password=password, port=port)
        stdin, stdout, stderr = client.exec_command(command)
        data = stdout.read() + stderr.read()
        client.close()
        data = str(data).replace('\\n', '\n').replace('\\t', '\t')[2:-1]
        logging.info("Команда успешно выполнена")
        return data
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с Linux: %s", error)
        return "Не удалось установить соединение"

def db(command: str, username: str, password: str, host: str, port: str, database: str, type: str):
    connection = None
    result = ''

    try:
        connection = psycopg2.connect(user=username, password=password, host=host, port=port, database=database)
        cursor = connection.cursor()
        cursor.execute(command)
        if type == 'select':
            data = cursor.fetchall()
            for row in data:
                result += str(row[0]) + '. ' + str(row[1]) + '\n'
                logging.info("Команда успешно выполнена")
        elif type == 'insert':
            connection.commit()
        logging.info("Команда успешно выполнена")
        logging.info(result)
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с PostgreSQL: %s", error)
        return "Ошибка при работе с PostgreSQL"
    finally:
        if connection is not None:
            cursor.close()
            connection.close()
        if result:
            return result
        return "Ошибка при работе с PostgreSQL"

def get_emails(update: Update, context):
    update.message.reply_text(db('SELECT * FROM email_table;', DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE, 'select'))

def get_phone_numbers(update: Update, context):
    update.message.reply_text(db('SELECT * FROM phone_table;', DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_DATABASE, 'select'))

def get_release(update: Update, context):
    update.message.reply_text(linux('cat /proc/version', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_uname(update: Update, context):
    update.message.reply_text(linux('uname -o -n -r -v -p', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_uptime(update: Update, context):
    update.message.reply_text(linux('uptime', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_df(update: Update, context):
    update.message.reply_text(linux('df -a -h', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_free(update: Update, context):
    update.message.reply_text(linux('free -h', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_mpstat(update: Update, context):
    update.message.reply_text(linux('mpstat -P ALL', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_w(update: Update, context):
    update.message.reply_text(linux('w', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_auths(update: Update, context):
    update.message.reply_text(linux('last -n 10', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_critical(update: Update, context):
    update.message.reply_text(linux('journalctl -p crit -n 5', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_ps(update: Update, context):
    update.message.reply_text(linux('ps -A | head -n 11', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_ss(update: Update, context):
    update.message.reply_text(linux('ss -s', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_services(update: Update, context):
    update.message.reply_text(linux('systemctl list-units --type=service | head -n 10', RM_HOST, RM_USER, RM_PASSWORD, RM_PORT))

def get_repl_logs(update: Update, context): 
    try:
	# docker
        # command = "cat /var/log/postgresql/postgresql-15-main.log | grep repl | tail -n 20"
        # ansible 
        command = "cat /var/log/postgresql/postgresql-14-main.log | grep repl | tail -n 20"

        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        update.message.reply_text(result.stdout, result.stderr)
    except subprocess.CalledProcessError as e:
        update.message.reply_text(e.stdout, e.stderr)

def main():
    updater = Updater(token, use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    # Обработчики диалога
    convHandlerFindEmails = ConversationHandler(
        entry_points=[CommandHandler('find_email', findEmailsCommand)],
        states={
            'findEmails': [MessageHandler(Filters.text & ~Filters.command, findEmails)],
            'saveEmails': [MessageHandler(Filters.text & ~Filters.command, saveEmails)]
        },
        fallbacks=[]
    )

    convHandlerFindPhoneNumbers = ConversationHandler(
        entry_points=[CommandHandler('find_phone_number', findPhoneNumbersCommand)],
        states={
            'findPhoneNumbers': [MessageHandler(Filters.text & ~Filters.command, findPhoneNumbers)],
            'savePhoneNumbers':  [MessageHandler(Filters.text & ~Filters.command, savePhoneNumbers)]
        },
        fallbacks=[]
    )

    convHandlerVerifyPassword = ConversationHandler(
        entry_points=[CommandHandler('verify_password', verifyPasswordCommand)],
        states={
            'verifyPassword': [MessageHandler(Filters.text & ~Filters.command, verifyPassword)],
        },
        fallbacks=[]
    )

    convHandlerAppList = ConversationHandler(
        entry_points=[CommandHandler('get_apt_list', get_app_list_command)],
        states={
            'get_app_list_choice': [MessageHandler(Filters.text & ~Filters.command, get_app_list_choice)],
            'get_app_info': [MessageHandler(Filters.text & ~Filters.command, get_app_info)],
        },
        fallbacks=[]
    )

	# Регистрируем обработчики команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("get_release", get_release))
    dp.add_handler(CommandHandler("get_uname", get_uname))
    dp.add_handler(CommandHandler("get_uptime", get_uptime))
    dp.add_handler(CommandHandler("get_df", get_df))
    dp.add_handler(CommandHandler("get_free", get_free))
    dp.add_handler(CommandHandler("get_mpstat", get_mpstat))
    dp.add_handler(CommandHandler("get_w", get_w))
    dp.add_handler(CommandHandler("get_auths", get_auths))
    dp.add_handler(CommandHandler("get_critical", get_critical))
    dp.add_handler(CommandHandler("get_ps", get_ps))
    dp.add_handler(CommandHandler("get_ss", get_ss))
    dp.add_handler(CommandHandler("get_services", get_services))
    dp.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    dp.add_handler(CommandHandler("get_emails", get_emails))
    dp.add_handler(CommandHandler("get_phone_numbers", get_phone_numbers))
    dp.add_handler(CommandHandler("help", helpCommand))
    dp.add_handler(convHandlerFindEmails)
    dp.add_handler(convHandlerFindPhoneNumbers)
    dp.add_handler(convHandlerVerifyPassword)
    dp.add_handler(convHandlerAppList)

	# Регистрируем обработчик текстовых сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

	# Запускаем бота
    updater.start_polling()

	# Останавливаем бота при нажатии Ctrl+C
    updater.idle()


if __name__ == '__main__':
    main()
