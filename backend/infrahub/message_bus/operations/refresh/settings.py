from infrahub import config
from infrahub.log import get_logger
from infrahub.message_bus import messages


async def response_delay(message: messages.RefreshSettingsResponseDelay) -> None:
    config.SETTINGS.miscellaneous.response_delay = message.response_delay
    get_logger().info("Updated API response delay", response_delay=message.response_delay)
