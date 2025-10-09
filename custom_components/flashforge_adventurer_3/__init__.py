import asyncio
import logging
import socket
from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.config_entries import SOURCE_DISCOVERY

# Flashforge custom UDP port
DISCOVERY_PORT = 18001
DISCOVERY_TIMEOUT = 300
UDP_IP = "225.0.0.9"
UDO_PORT = 19000

logger = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data['unsub_options_update_listener'] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # Forward the setup to the sensor and camera platforms.
    try:
      await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "camera"])
    except asyncio.TimeoutError as ex:
      raise ConfigEntryNotReady(f"Timeout while loading config entry for sensor") from ex
    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, 'sensor')],
            *[hass.config_entries.async_forward_entry_unload(entry, 'camera')],
        )
    )
    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]['unsub_options_update_listener']()

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the GitHub Custom component from yaml configuration."""
    hass.data.setdefault(DOMAIN, {})

    # 1. Start the UDP Listener Task
    hass.loop.create_task(flashforge_discovery(hass))
    
    return True

async def flashforge_discovery(hass: HomeAssistant):
    # We use a standard socket for custom UDP listening
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(5)
    sock.setblocking(False)
    
    # The printer may broadcast to a multicast address (e.g., 255.0.0.9)
    # or just to the broadcast address (255.255.255.255). We bind to the discovery port.
    try:
        sock.bind((sock.gethostbyname(socket.gethostname()), DISCOVERY_PORT))
    except OSError as err:
        logger.error("Failed to bind UDP socket on port {DISCOVERY_PORT}: {err}")
        return

    logger.debug("Starting Flashforge UDP discovery listener on port {DISCOVERY_PORT}")

    while True:
        try:
            # Use hass.loop.sock_recvfrom for non-blocking asynchronous I/O
            data, addr = await hass.loop.sock_recvfrom(sock, 1024)
            host = addr[0]

            # 2. Process the received data
            # The 'data' payload will be the custom Flashforge ID packet.
            if not data.startswith(b'Adventurer'): # Placeholder check
                logger.debug("Received unknown UDP data from {host}")
                continue

            # 3. Initiate the Configuration Flow
            # The data passed to the config flow will be the discovered IP address.
            logger.info("Flashforge Adventurer discovered at {host}")
            
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_DISCOVERY},
                    data={CONF_HOST: host},
                )
            )

        except (socket.error, asyncio.TimeoutError) as err:
            logger.warning(f"Flashforge discovery error: {err}")
        
        # A small delay to keep the loop responsive
        await asyncio.sleep(DISCOVERY_TIMEOUT)
