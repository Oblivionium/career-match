import os

from dotenv import load_dotenv
from google import genai
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
agent_seed = os.getenv("AGENT_SEED")

if not gemini_api_key:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

if not agent_seed:
    raise RuntimeError("AGENT_SEED is missing from .env")

client = genai.Client(api_key=gemini_api_key)

agent = Agent(
    name="fetchathon_agent",
    seed=agent_seed,
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)

chat_protocol = Protocol(spec=chat_protocol_spec)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Agent address: {ctx.agent.address}")


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(
    ctx: Context,
    sender: str,
    msg: ChatMessage,
):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    user_text = "\n".join(
        item.text
        for item in msg.content
        if isinstance(item, TextContent)
    ).strip()

    if not user_text:
        response = "Please send a text message."
    else:
        try:
            result = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_text,
            )

            response = result.text or "I couldn't generate a response."

        except Exception:
            ctx.logger.exception("Gemini request failed")
            response = "Sorry, I couldn't process that request. Please try again."

    await ctx.send(
        sender,
        ChatMessage(
            content=[
                TextContent(type="text", text=response),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_acknowledgement(
    ctx: Context,
    sender: str,
    msg: ChatAcknowledgement,
):
    ctx.logger.info(f"Message acknowledged by {sender}")


agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()