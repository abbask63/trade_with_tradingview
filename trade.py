# coding=utf-8
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from tradingview_ta import TA_Handler, Interval
from requests import Session
import numpy as np
import talib
import os
from datetime import datetime  # Importing the datetime module

# from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Initialization
TOKEN = ':'  # کلید ربات تلگرام را وارد کنید
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher
session = Session()
session.headers.update({'Accepts': 'application/json'})

# File to store user_list
USER_FILE = 'users.txt'

# Function to load users list from file
def load_users():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w', encoding='utf-8') as f:
            f.write('')
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        users = f.read().splitlines()
    return users

# Function to save users list to file
def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        for user in users:
            f.write(user + '\n')

# Function to reload users
def reload_users():
    global users_list
    users_list = load_users()

# Load initial users list
users_list = load_users()

# If the list is empty, initialize with default users
if not users_list:
    users_list = ['@user1', '@user2', '@user3']
    save_users(users_list)

# Admin username
ADMIN_USERNAME = 'adminuser'

# Functions
def is_user_allowed(user):
    username = f"@{user.username}" if user.username else user.first_name
    return username in users_list or user.first_name in users_list

def button_handler(update, context):
    query = update.callback_query
    query.answer()  # ضروری برای پاسخ دادن به callback_query
    user = query.from_user
    is_admin = (user.username == ADMIN_USERNAME)

    # Determine if the user is allowed to proceed based on their action
    action = context.user_data.get('action')

    if query.data == 'analyze':
        analyze_crypto(update, context)
    elif query.data == 'add_user' and is_admin:
        context.bot.send_message(chat_id=query.message.chat_id, text='لطفا نام کاربری را برای افزودن وارد کنید (با @).')
        context.user_data['action'] = 'add_user'
    elif query.data == 'remove_user' and is_admin:
        current_users = load_users()
        buttons = []
        for user_entry in current_users:
            if user_entry != f"@{ADMIN_USERNAME}":
                buttons.append([InlineKeyboardButton(user_entry, callback_data=f'remove_{user_entry}')])
        buttons.append([InlineKeyboardButton("بازگشت", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(buttons)
        context.bot.send_message(chat_id=query.message.chat_id, text='کاربران موجود:', reply_markup=reply_markup)
    elif query.data.startswith('remove_') and is_admin:
        user_to_remove = query.data.split('_', 1)[1]
        current_users = load_users()
        if user_to_remove in current_users:
            current_users.remove(user_to_remove)
            save_users(current_users)
            reload_users()  # Reload the user list after removing a user
            context.bot.send_message(chat_id=query.message.chat_id, text=f'کاربر {user_to_remove} حذف شد.')
        else:
            context.bot.send_message(chat_id=query.message.chat_id, text='کاربر یافت نشد.')
    elif query.data == 'reload_users' and is_admin:
        reload_users()
        context.bot.send_message(chat_id=query.message.chat_id, text='لیست کاربران بارگذاری شد.')
    elif query.data == 'back':
        start(update, context)
    else:
        # Only call search_crypto if no specific action is set
        if action is None:
            context.bot.send_message(chat_id=query.message.chat_id, text='گزینه نامعتبر.')

def trading_view(crypto, timee):
    handler = TA_Handler()
    handler.set_symbol_as(crypto)
    handler.set_exchange_as_crypto_or_stock("BINANCE")
    handler.set_screener_as_crypto()
    handler.set_interval_as(timee)
    
    try:
        analysis = handler.get_analysis()
        
        if analysis is None:  # بررسی وجود تحلیل
            return "null"  # در صورت عدم وجود تحلیل، null برمی‌گرداند
        
        recommendation = analysis.summary.get("RECOMMENDATION")
        if recommendation is None:
            return "null"  # در صورت عدم وجود توصیه، null برمی‌گرداند

        return recommendation
    
    except Exception as e:
        return f"خطا در دریافت تحلیل"


def get_bars(symbol, interval, limit):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
    try:
        data = session.get(url).json()
        return np.array(data, dtype=float)
    except Exception as e:
        return None

def mfi(crypto, timee):   
    bars = get_bars(crypto, timee, 1000)
    if bars is not None:
        return talib.MFI(bars[:, 2], bars[:, 3], bars[:, 4], bars[:, 5], timeperiod=14)[-1]
    else:
        return "خطا در دریافت داده‌های نمودار"

def get_price(symbol):
    url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
    try:
        response = session.get(url)
        data = response.json()
        return float(data['price'])
    except Exception as e:
        return None

def start(update, context):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = (user.username == ADMIN_USERNAME)

    allowed = is_user_allowed(user)

    if allowed:
        # Create main buttons
        reply_buttons = [
            [KeyboardButton("تحلیل رمز ارز")],
        ]

        if is_admin:
            # Add admin buttons
            reply_buttons += [
                [KeyboardButton("نمایش لیست کاربران")],
                [KeyboardButton("افزودن کاربر")],
                [KeyboardButton("حذف کاربر")],
                [KeyboardButton("بارگذاری مجدد کاربران")],
            ]

        reply_markup = ReplyKeyboardMarkup(reply_buttons, resize_keyboard=True)

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'سلام {username} به ربات تریدر خوش آمدید.\nلطفا گزینه مورد نظر را انتخاب کنید:',
            reply_markup=reply_markup
        )
    else:
        # For unauthorized users, only send access denial message
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='شما مجاز به استفاده از ربات نیستید. لطفا با پشتیبانی تماس حاصل فرمایید.'
        )

    # Create the support contact button as an InlineKeyboardButton
    support_button = InlineKeyboardButton("ارتباط با پشتیبانی", url='https://t.me/adminuser')
    support_markup = InlineKeyboardMarkup([[support_button]])

    # Send the support contact button separately
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='جهت ارتباط با پشتیبانی:',
        reply_markup=support_markup
    )



def help1(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, 
                             text='برای استفاده از ربات با مدیر ربات هماهنگ شوید @adminuser')

def analyze_crypto(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text='لطفا نام رمز ارز (مثلا BTC) را وارد کنید.')

def search_crypto(update, context):
    query = update.message.text.strip().upper()  # Remove spaces and convert to uppercase
    crypto_symbol = f"{query}USDT"  # Append USDT to the crypto symbol

    price = get_price(crypto_symbol)
    if price is None:
        context.bot.send_message(chat_id=update.message.chat_id, text='خطا در دریافت قیمت رمز ارز. لطفا دوباره تلاش کنید.')
        return

    # Get the current date
    # current_date = datetime.now().strftime("%Y-%m-%d %H:%M")  # Format: YYYY-MM-DD
    current_date = datetime.now().strftime("%H:%M  %d-%m-%Y")  # Format: YYYY-MM-DD

    # Get recommendations for different timeframes
    recommendations = {
        "هفتگی": trading_view(crypto_symbol, Interval.INTERVAL_1_WEEK),
        "روزانه": trading_view(crypto_symbol, Interval.INTERVAL_1_DAY),
        "4 ساعته": trading_view(crypto_symbol, Interval.INTERVAL_4_HOURS),
        "1 ساعته": trading_view(crypto_symbol, Interval.INTERVAL_1_HOUR),
        "15 دقیقه": trading_view(crypto_symbol, Interval.INTERVAL_15_MINUTES),
    }

    # Send message to user showing symbol, date, and price
    response_message = f'🔹 {query} :\n📅 تاریخ: {current_date}\n💰 قیمت: {price} USDT\n' + \
                       '\n'.join(f'🖋️ شاخص {timeframe}: {rec}' for timeframe, rec in recommendations.items())

    context.bot.send_message(chat_id=update.message.chat_id, text=response_message)


def list_users(update, context):
    current_users = load_users()
    if current_users:
        user_list = "\n".join(current_users)
        context.bot.send_message(chat_id=update.message.chat_id, text=f"لیست کاربران:\n{user_list}")
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="هیچ کاربری وجود ندارد.")

def handle_message(update, context):
    user = update.message.from_user
    is_admin = (user.username == ADMIN_USERNAME)
    allowed = is_user_allowed(user)
    action = context.user_data.get('action')

    if allowed:
        if action == 'add_user' and is_admin:
            new_user = update.message.text.strip()
            if not new_user.startswith('@'):
                new_user = '@' + new_user
            current_users = load_users()
            if new_user in current_users:
                context.bot.send_message(chat_id=update.message.chat_id, text='این کاربر قبلاً وجود دارد.')
            else:
                current_users.append(new_user)
                save_users(current_users)
                reload_users()  # Reload the user list after adding a new user
                context.bot.send_message(chat_id=update.message.chat_id, text=f'کاربر {new_user} افزوده شد.')
            context.user_data['action'] = None
        elif update.message.text == "تحلیل رمز ارز":
            analyze_crypto(update, context)
        elif update.message.text == "افزودن کاربر" and is_admin:
            context.bot.send_message(chat_id=update.message.chat_id, text='لطفا نام کاربری را برای افزودن وارد کنید (با @).')
            context.user_data['action'] = 'add_user'
        elif update.message.text == "حذف کاربر" and is_admin:
            current_users = load_users()
            buttons = []
            for user_entry in current_users:
                if user_entry != f"@{ADMIN_USERNAME}":
                    buttons.append([InlineKeyboardButton(user_entry, callback_data=f'remove_{user_entry}')])
            buttons.append([InlineKeyboardButton("بازگشت", callback_data='back')])
            reply_markup = InlineKeyboardMarkup(buttons)
            context.bot.send_message(chat_id=update.message.chat_id, text='کاربران موجود:', reply_markup=reply_markup)
        elif update.message.text == "بازگشت":
            start(update, context)
        elif update.message.text == "بارگذاری مجدد کاربران" and is_admin:
            reload_users()  # Reload the user list
            context.bot.send_message(chat_id=update.message.chat_id, text='لیست کاربران بارگذاری شد.')
        elif update.message.text == "نمایش لیست کاربران":
            list_users(update, context)
        elif update.message.text == "ارتباط با پشتیبانی":  # Allow support button message to be recognized
            context.bot.send_message(chat_id=update.message.chat_id, text='جهت ارتباط با پشتیبانی: https://t.me/adminuser')
        else:
            search_crypto(update, context)
    else:
        # Unauthorized users can also see the support message
        context.bot.send_message(
            chat_id=update.message.chat_id,
            
            text='شما مجاز به استفاده از ربات نیستید لطفا با پشتیبانی تماس بگیرید https://t.me/adminuser'
        )


# Handlers
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('help', help1))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(button_handler))  # اضافه کردن CallbackQueryHandler

# Start the bot
updater.start_polling()
updater.idle()
