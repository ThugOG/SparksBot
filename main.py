import os
import logging
import telebot
from telebot import types
import requests
from io import BytesIO
from keep_alive import keep_alive

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your Telegram Bot Token
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Your Telegram User ID (messages will be forwarded to this ID)
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# User states dictionary to track conversation state
user_states = {}
user_data = {}

# Define states
STATE_QUESTION = 1
STATE_DESCRIPTION = 2
STATE_IMAGE = 3

@bot.message_handler(commands=['start'])
def start(message):
    """Send welcome message with information about Trepa and available commands."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    spark_button = types.KeyboardButton('/sendspark')
    markup.add(spark_button)

    welcome_message = (
        f"Hey {message.from_user.first_name}, welcome to Trepa Bot! ⚡️\n\n"
        f"Trepa is the world's first sentiment prediction platform powered by *prediction pools*, not markets.\n\n "
        f"Got a question burning in your head? Use /sendspark to submit a *spark* — our experts will decode the collective signal behind it.\n\n"
        f"Let’s make your curiosity count. ✨"
    )

    bot.send_message(
        message.chat.id,
        welcome_message,
        reply_markup=markup,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    """Provide help information about the bot."""
    help_text = (
        "🛠 *Need help?* Here's how to use Trepa Bot:\n\n"
        "• /start – Introduction to Trepa and what this bot can do\n"
        "• /sendspark – Submit a *spark* (your thought-provoking question)\n"
        "• /cancel – Stop the current spark submission\n"
        "• /help – See this guide again\n\n"
        "*What’s a spark?*\n"
        "It’s a signal you send to Trepa’s prediction pool — a hypothesis, a trend, a social whisper. "
        "We help distill sentiment from it and surface insights before they go mainstream.\n\n"
        "When you use /sendspark, I’ll ask:\n"
        "1. Your question\n"
        "2. Some background/context\n"
        "3. (Optional) An image or link that captures the vibe\n\n"
        "Let’s turn collective sentiment into superpowers. 🔮"
    )

    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['sendspark'])
def send_spark(message):
    """Start the question submission process."""
    user_id = message.from_user.id
    user_states[user_id] = STATE_QUESTION
    user_data[user_id] = {}

    bot.send_message(
        message.chat.id,
        "Let's ignite a spark. 🔥\n\n"
        "What’s your question or hypothesis?\n\n"
        "Note: Trepa isn’t a fortune-teller. Avoid asking us to *predict the future*. "
        "Instead, focus on ideas, trends, or moments where public sentiment might be shifting."
    )

@bot.message_handler(commands=['cancel'])
def cancel(message):
    """Cancel the conversation."""
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_data:
        del user_data[user_id]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    spark_button = types.KeyboardButton('/sendspark')
    markup.add(spark_button)

    bot.send_message(
        message.chat.id,
        "No worries — your spark submission has been cancelled. 🔕\n\n"
        "You can always light another one with /sendspark whenever inspiration strikes.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    """Handle all messages according to the user's state."""
    user_id = message.from_user.id

    # If user hasn't started a question process, remind them to use /sendspark
    if user_id not in user_states:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        spark_button = types.KeyboardButton('/sendspark')
        markup.add(spark_button)

        bot.send_message(
            message.chat.id, 
            "To submit a question, please use the /sendspark command.",
            reply_markup=markup
        )
        return

    state = user_states[user_id]

    if state == STATE_QUESTION:
        # User is providing their question
        user_data[user_id]['question'] = message.text
        user_states[user_id] = STATE_DESCRIPTION

        bot.send_message(
            message.chat.id,
            "Great question! 📌\n\n"
            "Now give us a bit more context — where’s this coming from? A tweet? A trend? A gut feeling?\n"
            "Tell us what inspired the spark."
        )

    elif state == STATE_DESCRIPTION:
        # User is providing description/context
        user_data[user_id]['description'] = message.text
        user_states[user_id] = STATE_IMAGE

        bot.send_message(
            message.chat.id,
            "Thanks for the background! 🧠\n\n"
            "Do you have an image or screenshot that captures the essence of this spark?\n\n"
            "Drop the image link here (or upload a photo). If not, just type 'no'."
        )

    elif state == STATE_IMAGE:
        # User responded to image request with text
        text = message.text.lower()
        if text in ['no', 'none', 'n']:
            # User doesn't have an image
            finalize_question(message, user_id, has_image=False)
        elif text.startswith(('http://', 'https://')):
            # User provided an image URL
            user_data[user_id]['image_url'] = message.text
            finalize_question(message, user_id, has_image=True)
        else:
            # User provided some text but not a URL
            user_data[user_id]['additional_info'] = message.text
            finalize_question(message, user_id, has_additional_info=True)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Handle photos sent by users."""
    user_id = message.from_user.id

    if user_id not in user_states:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        spark_button = types.KeyboardButton('/sendspark')
        markup.add(spark_button)

        bot.send_message(
            message.chat.id,
            "To submit a question with an image, please use the /sendspark command first.",
            reply_markup=markup
        )
        return

    state = user_states[user_id]

    if state == STATE_IMAGE:
        # User sent an actual photo
        user_data[user_id]['image_id'] = message.photo[-1].file_id
        finalize_question(message, user_id, has_image=True)
    else:
        # User sent an image at the wrong time
        bot.send_message(
            message.chat.id,
            "I wasn't expecting an image at this point. Please follow the prompts."
        )

def finalize_question(message, user_id, has_image=False, has_additional_info=False):
    """Forward the complete question to the admin."""
    user = message.from_user
    question_text = user_data[user_id].get('question', 'No question provided')
    description_text = user_data[user_id].get('description', 'No description provided')

    # Prepare the message to send to admin
    admin_message = (
        f"🌟 NEW SPARK RECEIVED 🌟\n\n"
        f"User: {user.first_name} {' ' + user.last_name if user.last_name else ''} "
        f"(@{user.username if user.username else 'no username'})\n"
        f"User ID: {user.id}\n\n"
        f"Question: {question_text}\n\n"
        f"Description/Source: {description_text}"
    )

    # Add additional info if provided
    if has_additional_info and 'additional_info' in user_data[user_id]:
        admin_message += f"\n\nAdditional Info: {user_data[user_id]['additional_info']}"

    # Handle image if provided
    if 'image_id' in user_data[user_id]:
        # Forward the actual image with caption to admin
        bot.send_photo(
            chat_id=ADMIN_USER_ID,
            photo=user_data[user_id]['image_id'],
            caption=admin_message
        )
    elif 'image_url' in user_data[user_id]:
        # User provided an image URL
        image_url = user_data[user_id]['image_url']
        admin_message += f"\n\nImage URL: {image_url}"

        try:
            # Try to download and send the image
            response = requests.get(image_url)
            if response.status_code == 200:
                # Send image if download was successful
                bot.send_photo(
                    chat_id=ADMIN_USER_ID,
                    photo=BytesIO(response.content),
                    caption=admin_message
                )
            else:
                # If download failed, just send the URL
                bot.send_message(chat_id=ADMIN_USER_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            # If any error occurs, just send the URL
            bot.send_message(chat_id=ADMIN_USER_ID, text=admin_message)
    else:
        # No image provided
        bot.send_message(chat_id=ADMIN_USER_ID, text=admin_message)

    # Respond to the user
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    spark_button = types.KeyboardButton('/sendspark')
    markup.add(spark_button)

    bot.send_message(
        message.chat.id,
        "🧠 Thanks! Your question has been submitted to Trepa HQ.\n\nWe’ll use it to spark community sentiment. "
        "If it fits, it may show up on Trepa soon for others to weigh in.\n\nWant to ask another one? Hit /sendspark anytime!",
        reply_markup=markup
    )

    # Clear user data
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_data:
        del user_data[user_id]

def main():
    keep_alive()  # 👈 this line goes before polling
    bot.infinity_polling()  

if __name__ == "__main__":
    main()
