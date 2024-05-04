from groq import Groq
from dotenv import load_dotenv
import os
from telegram.ext import ContextTypes

load_dotenv()

# Create a ChatBot
chatbot = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)


def generate_response(message: str, context: ContextTypes.DEFAULT_TYPE):
    """Generate a response to a message"""
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "user",
            "content": message,
        }
    ]
    response_queue = ""
    for resp in chatbot.chat.completions.create(
        messages=context.user_data.get("messages"),
        model=context.user_data.get("model", "llama3-8b-8192"),
        stream=True,
    ):
        if resp.choices[0].delta.content:
            response_queue += resp.choices[0].delta.content
        if len(response_queue) > 100:
            yield response_queue
            response_queue = ""
    yield response_queue
