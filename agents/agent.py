from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)


agent = Agent(
    name="fetchathon_agent",
    port=8001,
)

chat_protocol = Protocol(spec=chat_protocol_spec)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("Fetch-A-Thon agent started")
    ctx.logger.info(f"Agent address: {ctx.agent.address}")


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(
    ctx: Context,
    sender: str,
    msg: ChatMessage,
):
    # Acknowledge receipt of the incoming message.
    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Extract all text blocks from the incoming message.
    user_text = "\n".join(
        item.text
        for item in msg.content
        if isinstance(item, TextContent)
    ).strip()

    ctx.logger.info(f"Received message from {sender}: {user_text}")

    if not user_text:
        response = "Please send a text message."
    else:
        response = f"Your message was received: {user_text}"

    # Return one response and end the conversation turn.
    await ctx.send(
        sender,
        ChatMessage(
            content=[
                TextContent(
                    type="text",
                    text=response,
                ),
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
    ctx.logger.info(
        f"Received acknowledgement from {sender} "
        f"for message {msg.acknowledged_msg_id}"
    )


agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
