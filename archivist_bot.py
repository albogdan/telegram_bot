from datetime import datetime, timezone
import json
import logging
import os.path
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
)
from telegram.ext import filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

LOCAL_TZ = pytz.timezone("America/Toronto")

# The token to access the bot
BOT_TOKEN = os.environ["BOT_TOKEN"]

# The ID of the spreadsheet.
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def append_values_to_spreadsheet(
    spreadsheet_id, range_name, value_input_option, values
):
    """
    Creates the batch_update the user has access to.
    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
    """
    logging.info("Getting Google credentials")
    creds = get_credentials()

    try:
        service = build("sheets", "v4", credentials=creds)

        # [END_EXCLUDE]
        body = {"values": values}
        logging.info("Sending data to spreadsheet")
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )
        logging.info(f"{(result.get('updates').get('updatedCells'))} cells appended.")
        return True

    except HttpError as error:
        logging.error(f"An error occurred: {error}")
        return False


def get_credentials():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        logging.info("Using existing token.json")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        logging.info("Refreshing token.json")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Send start message")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome to the dank maymes archivist bot!",
    )


async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Send usage message")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="To archive a message, simply reply to the message and tag this bot!",
    )


async def receive_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Received command to upload quote")
    logging.debug(f"Update: {update}")
    reply_message = update.message.reply_to_message
    message_text = update.message.text
    if (
        hasattr(reply_message, "text")
        and reply_message.text is not None
        and message_text == "@dank_maymes_bot"
    ):
        logging.info("Quote has text to upload")
        logging.info(
            f"Message: {reply_message.text} | From: {reply_message.from_user.first_name} {reply_message.from_user.last_name} |"
            f"Sent at: {reply_message.date.astimezone(LOCAL_TZ)}"
        )

        date_str = reply_message.date.astimezone(LOCAL_TZ).date().strftime("%Y-%m-%d")
        values = [
            [
                reply_message.text,
                f"{reply_message.from_user.first_name}",
                date_str,
            ]
        ]
        logging.info("Sending data to google sheets function")
        status = append_values_to_spreadsheet(
            SPREADSHEET_ID, "A2:C2", "USER_ENTERED", values
        )
        if status:
            logging.info("Quote saved successfully")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Quote by {reply_message.from_user.first_name} saved successfully!",
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Could not save quote. Please try again!",
            )

    else:
        logging.info("Invalid message to archive")


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    start_handler = CommandHandler("start", start)
    usage_handler = CommandHandler("usage", usage)
    receive_quote_handler = MessageHandler(
        filters.TEXT & (~filters.COMMAND), receive_quote
    )

    application.add_handler(start_handler)
    application.add_handler(usage_handler)
    application.add_handler(receive_quote_handler)

    application.run_polling()
