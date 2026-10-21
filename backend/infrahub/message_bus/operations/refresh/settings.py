from infrahub import config
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.trace import clear_temporary_sample_ratio, set_temporary_sample_ratio


async def response_delay(message: messages.RefreshSettingsResponseDelay) -> None:
    config.SETTINGS.miscellaneous.response_delay = message.response_delay
    get_logger().info("Updated API response delay", response_delay=message.response_delay)


async def trace_sample_ratio(message: messages.RefreshSettingsTraceSampleRatio) -> None:
    if message.ratio is None or message.expires_at is None:
        clear_temporary_sample_ratio()
        get_logger().info("Cleared the temporary trace sampling ratio")
        return
    set_temporary_sample_ratio(ratio=message.ratio, expires_at=message.expires_at)
    get_logger().info(
        "Set the temporary trace sampling ratio", ratio=message.ratio, expires_at=message.expires_at.isoformat()
    )
