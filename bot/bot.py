import os
import re
import paramiko
import psycopg2
import logging
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler


logging.basicConfig(filename='bot.log', level=logging.DEBUG, format=' %(asctime)s - %(name)s - %(levelname)s - %(message)s', encoding="utf-8")
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('TOKEN')
HOST = os.getenv('RM_HOST')
SSH_PORT = os.getenv('RM_PORT')
SSH_USER = os.getenv('RM_USER')
SSH_PASSWORD = os.getenv('RM_PASSWORD')

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_DATABASE')
DB_HOST = os.getenv("DB_HOST")


def connect_db():
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        logger.info("Connected to PostgreSQL database successfully")
        logger.info(f"user={DB_USER}, password={DB_PASSWORD} host={DB_HOST}, port={DB_PORT}, database={DB_NAME}")
        return connection
    except Exception as e:
        logger.error(f"Error connecting to the database: {str(e)}", exc_info=True)
        raise

# Функция для выполнения SQL-запросов
def execute_sql_query(query, connection=None):
    try:
        needs_closing = 0
        if not connection:
            connection = connect_db()
            needs_closing = 1
        cursor = connection.cursor()
        cursor.execute(query)
        try:
            c = cursor.fetchall()
        except:
            c = None
        connection.commit()
        logger.info("SQL query executed successfully")
        return c
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}", exc_info=True)
        connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if needs_closing:
            connection.close()

def start(update: Update, context):
    user = update.effective_user
    update.message.reply_text(f'Привет {user.full_name}!\nСписок команд доступен в /help')

def helpCommand(update: Update, context):
    logger.debug("Answering help command")
    command_list = ['start', 'help', 'find_email', 'find_phone_number', 'get_repl_logs',
                    'get_emails', 'get_phone_numbers', 'verify_password', 'get_release',
                    'get_uname', 'get_uptime', 'get_df', 'get_free', 'get_mpstat',
                    'get_w', 'get_auths', 'get_critical', 'get_ps', 'get_ss', 'get_apt_list',
                    'get_apt_list <package_name>', 'get_services' ]
    command_list_str = "\n".join(['/'+x for x in command_list])
    update.message.reply_text(f'Доступные команды:\n{command_list_str}')

def verifyPasswordCommand(update: Update, context):
    logger.debug("Answering verify_password command")
    update.message.reply_text('Введите пароль для проверки сложности: ')
    return 'verifyPassword'

def verifyPassword(update: Update, context):
    password = update.message.text
    logger.debug(f"Recieved password to test: {password}")
    if re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
        update.message.reply_text('Пароль сложный')
        logger.debug("Password is strong")
    else:
        update.message.reply_text('Пароль простой')
        logger.debug("Password is weak")
    return ConversationHandler.END # Завершаем работу обработчика диалога

def findEmailsCommand(update: Update, context):
    logger.debug("Answering find_emails command")
    update.message.reply_text('Введите текст для поиска email адресов: ')
    return 'findEmails'

def findEmails(update: Update, context):
    user_input = update.message.text
    logger.debug(f"Recieved text to search for emails: {user_input}")
    email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    email_list = email_regex.findall(user_input)
    logger.debug(f"Emails found: {email_list}")
    if not email_list:
        update.message.reply_text('Email адреса не найдены')
        return ConversationHandler.END
   
    else:
        emails = '\n'.join([str(i + 1) + '. ' + x for i, x in enumerate(email_list)])
        update.message.reply_text(emails)
        # Предложение записи найденных email адресов в базу данных
        update.message.reply_text("Хотите сохранить найденные email адреса в базе данных? (Да/Нет)")
        context.user_data["email_list"] = email_list
        return "confirm_email_save"
    
def confirm_email_save(update: Update, context):
    response = update.message.text.lower()
    email_list = context.user_data["email_list"]
    if response == "да":
        connection = connect_db()
        query = "INSERT INTO email_table (email) VALUES ('"
        query += "'), ('".join(email_list) + "');"
        msg = execute_sql_query(query, connection=connection)
        connection.close()
        update.message.reply_text("Email адреса успешно сохранены в базе данных.")
    else:
        update.message.reply_text("Email адреса не были сохранены в базе данных.")
    return ConversationHandler.END

def findPhoneNumbersCommand(update: Update, context):
    logger.debug("Answering find_phone_number command")
    update.message.reply_text('Введите текст для поиска телефонных номеров: ')
    return 'findPhoneNumbers'

def findPhoneNumbers (update: Update, context):
    user_input = update.message.text # Получаем текст, содержащий(или нет) номера телефонов
    logger.debug(f"Recieved text to search for phone numbers: {user_input}")
    phoneNumRegex = re.compile(r'(?:\+7|\b8)(?:[ -]?\(?)(\d{3})(?:\)?)(?:[ -]?)(\d{3})(?:[ -]?)(\d{2})(?:[ -]?)(\d{2}\b)')
    

    phoneNumberList = phoneNumRegex.findall(user_input) # Ищем номера телефонов

    if not phoneNumberList: # Обрабатываем случай, когда номеров телефонов нет
        update.message.reply_text('Телефонные номера не найдены')
        return ConversationHandler.END # Завершаем выполнение функции

    phoneNumbers = '' # Создаем строку, в которую будем записывать номера телефонов
    for i in range(len(phoneNumberList)):
        phoneNumbers += f'{i+1}. {" ".join(phoneNumberList[i])}\n' # Записываем очередной номер

    update.message.reply_text(phoneNumbers) # Отправляем сообщение пользователю

    update.message.reply_text("Хотите сохранить найденные номера телефонов в базе данных? (Да/Нет)")
    context.user_data["phoneNumberList"] = phoneNumberList
    return "confirm_phone_save"
     

def confirm_phone_save(update: Update, context):
    response = update.message.text.lower()
    phoneNumberList = context.user_data["phoneNumberList"]
    phoneNumbers = []
    for i in range(len(phoneNumberList)):
        phoneNumbers.append(" ".join(phoneNumberList[i]))
    if response == "да":
        connection = connect_db()
        query = "INSERT INTO phone_table (phone) VALUES ('"
        query += "'), ('".join(phoneNumbers) + "');"
        msg = execute_sql_query(query, connection=connection)
        connection.close()
        update.message.reply_text("Номера телефонов успешно сохранены в базе данных.")
    else:
        update.message.reply_text("Номера телефонов не были сохранены в базе данных.")
    return ConversationHandler.END 

def connect_ssh():
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD)
        logger.info("SSH connection established successfully")
        return client
    except Exception as e:
        logger.error(f"Error connecting to SSH: {str(e)}", exc_info=True)
        raise

def execute_ssh_command(client, command):
    try:
        logger.debug(f"executing SSH command: {command}")
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        return output
    except Exception as e:
        logger.error(f"Error executing SSH command: {str(e)}", exc_info=True)
        raise

def get_repl_logs(update, context):
    try:
        command = "cat /var/log/postgresql/postgresql-15-main.log | grep repl -B 1 -A 1| tail -n 80"
        
        logs = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logs = logs.stdout
        # Split the response into chunks
        chunk_size = 4096  # Adjust the chunk size as needed
        chunks = [logs[i:i+chunk_size] for i in range(0, len(logs), chunk_size)]

        # Send each chunk as a separate message
        for chunk in chunks:
            update.message.reply_text(chunk)
        
        logger.info("Retrieved information about installed packages")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about installed packages", exc_info=True)
    finally:
        if client:
            client.close()

def get_emails(update, context):
    
    msg = execute_sql_query("SELECT * from email_table;")
    msg = [str(i[0]) + ". " + str(i[1]) for i in msg]
    msg = '\n'.join(msg)
    # Split the response into chunks
    chunk_size = 4096  # Adjust the chunk size as needed
    chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]

    # Send each chunk as a separate message
    for chunk in chunks:
        update.message.reply_text(chunk)
    
    logger.info("Retrieved email_table table")

def get_phone_numbers(update, context):
    
    msg = execute_sql_query("SELECT * from phone_table;")
    msg = [str(i[0]) + ". " + str(i[1]) for i in msg]
    msg = '\n'.join(msg)
    # Split the response into chunks
    chunk_size = 4096  # Adjust the chunk size as needed
    chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]

    # Send each chunk as a separate message
    for chunk in chunks:
        update.message.reply_text(chunk)
    
    logger.info("Retrieved phone numbers table")

def get_release(update, context):
    try:
        client = connect_ssh()
        release = execute_ssh_command(client, 'lsb_release -a')
        update.message.reply_text(release)
        logger.info("Retrieved information about the system release")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about the system release", exc_info=True)
    finally:
        if client:
            client.close()

def get_uname(update, context):
    try:
        client = connect_ssh()
        uname = execute_ssh_command(client, 'uname -a')
        update.message.reply_text(uname)
        logger.info("Retrieved system information")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving system information", exc_info=True)
    finally:
        if client:
            client.close()

def get_uptime(update, context):
    try:
        client = connect_ssh()
        uptime = execute_ssh_command(client, 'uptime')
        update.message.reply_text(uptime)
        logger.info("Retrieved system uptime information")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving system uptime information", exc_info=True)
    finally:
        if client:
            client.close()

def get_df(update, context):
    try:
        client = connect_ssh()
        df = execute_ssh_command(client, 'df')
        update.message.reply_text(df)
        logger.info("Retrieved file system information")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving file system information", exc_info=True)
    finally:
        if client:
            client.close()

def get_free(update, context):
    try:
        client = connect_ssh()
        free = execute_ssh_command(client, 'free')
        update.message.reply_text(free)
        logger.info("Retrieved memory usage information")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving memory usage information", exc_info=True)
    finally:
        if client:
            client.close()

def get_mpstat(update, context):
    try:
        client = connect_ssh()
        mpstat = execute_ssh_command(client, 'mpstat')
        update.message.reply_text(mpstat)
        logger.info("Retrieved mpstat information")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving mpstat information", exc_info=True)
    finally:
        if client:
            client.close()

def get_w(update, context):
    try:
        client = connect_ssh()
        w = execute_ssh_command(client, 'w')
        update.message.reply_text(w)
        logger.info("Retrieved information about active users")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about active users", exc_info=True)
    finally:
        if client:
            client.close()

def get_auths(update, context):
    try:
        client = connect_ssh()
        auths = execute_ssh_command(client, 'last -n 10')
        update.message.reply_text(auths)
        logger.info("Retrieved information about recent logins")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about recent logins", exc_info=True)
    finally:
        if client:
            client.close()

def get_critical(update, context):
    try:
        client = connect_ssh()
        critical = execute_ssh_command(client, 'tail -n 5 /var/log/syslog')
        update.message.reply_text(critical)
        logger.info("Retrieved information about recent critical events")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about recent critical events", exc_info=True)
    finally:
        if client:
            client.close()

def get_ps(update, context):
    try:
        client = connect_ssh()
        ps = execute_ssh_command(client, 'ps aux')
        # Split the response into chunks
        chunk_size = 4096  # Adjust the chunk size as needed
        chunks = [ps[i:i+chunk_size] for i in range(0, len(ps), chunk_size)]

        # Send each chunk as a separate message
        for chunk in chunks:
            update.message.reply_text(chunk)
        logger.info("Retrieved information about running processes")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about running processes", exc_info=True)
    finally:
        if client:
            client.close()

def get_ss(update, context):
    try:
        client = connect_ssh()
        ss = execute_ssh_command(client, 'ss -tuln')
        update.message.reply_text(ss)
        logger.info("Retrieved information about used ports")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about used ports", exc_info=True)
    finally:
        if client:
            client.close()

def get_apt_list(update, context):
    try:
        client = connect_ssh()
        if context.args:
            package_name = ' '.join(context.args)
            apt_list = execute_ssh_command(client, f'apt show {package_name}')
        else:
            apt_list = execute_ssh_command(client, 'apt list --installed')

        # Split the response into chunks
        chunk_size = 4096  # Adjust the chunk size as needed
        chunks = [apt_list[i:i+chunk_size] for i in range(0, len(apt_list), chunk_size)]

        # Send each chunk as a separate message
        for chunk in chunks:
            update.message.reply_text(chunk)
        
        logger.info("Retrieved information about installed packages")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about installed packages", exc_info=True)
    finally:
        if client:
            client.close()

def get_services(update, context):
    try:
        client = connect_ssh()
        services = execute_ssh_command(client, 'service --status-all')
        update.message.reply_text(services)
        logger.info("Retrieved information about running services")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        logger.error("Error occurred while retrieving information about running services", exc_info=True)
    finally:
        if client:
            client.close()



def echo(update: Update, context):
    update.message.reply_text(f"Unknown command {update.message.text} !\n\nTry /help")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    logger.info("STARTING PROGRAM")
    # Обработка диалога email
    convHandlerFindEmails = ConversationHandler(
    entry_points=[CommandHandler('find_email', findEmailsCommand)],
    states={
        'findEmails': [MessageHandler(Filters.text & ~Filters.command, findEmails)],
        'confirm_email_save': [MessageHandler(Filters.text & ~Filters.command, confirm_email_save)],
    },
    fallbacks=[]
    )

    # Обработка диалога phone numbers
    convHandlerFindPhoneNumbers = ConversationHandler(
        entry_points=[CommandHandler('find_phone_number', findPhoneNumbersCommand)],
        states={
            'findPhoneNumbers': [MessageHandler(Filters.text & ~Filters.command, findPhoneNumbers)],
            'confirm_phone_save': [MessageHandler(Filters.text & ~Filters.command, confirm_phone_save)],
        },
        fallbacks=[]
    )

    # Обработка диалога password
    convHandlerVerifyPassword = ConversationHandler(
    entry_points=[CommandHandler('verify_password', verifyPasswordCommand)],
    states={
        'verifyPassword': [MessageHandler(Filters.text & ~Filters.command, verifyPassword)],
    },
    fallbacks=[]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", helpCommand))
    dp.add_handler(convHandlerFindEmails)
    dp.add_handler(convHandlerVerifyPassword)
    dp.add_handler(convHandlerFindPhoneNumbers)
    dp.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    dp.add_handler(CommandHandler("get_emails", get_emails))
    dp.add_handler(CommandHandler("get_phone_numbers", get_phone_numbers))

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
    dp.add_handler(CommandHandler("get_apt_list", get_apt_list))
    dp.add_handler(CommandHandler("get_services", get_services))

    # Регистрируем обработчик текстовых сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

