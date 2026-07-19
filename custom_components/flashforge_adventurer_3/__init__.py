import asyncio
import socket
from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.config_entries import SOURCE_DISCOVERY


import logging

# Flashforge custom UDP port
DISCOVERY_PORT:int = 18001
DISCOVERY_TIMEOUT:int = 10
DISCOVERY_INTERVAL:int = 300
UDP_IP:str = "225.0.0.9"
UDP_PORT:int = 19000

_LOGGER = logging.getLogger(__name__)

class FlashforgeDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol to handle Flashforge UDP discovery responses."""
    def __init__(self, hass: core.HomeAssistant):
        self.hass = hass

    def datagram_received(self, data, addr):
        host = addr[0]
        try:
            # Decode the response, adjust errors as needed based on printer output
            response = data.decode('utf-8', errors='ignore')
            _LOGGER.debug(f"Flashforge discovery response from {host}: {response}")
            
            # The python script just dumped the response. You might want to parse it here
            # to extract a serial number or mac address for a better unique_id.
            # For now, we will pass the host IP to the config flow.
            
            # Trigger the config flow discovery step
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_DISCOVERY},
                    data={"host": host}
                )
            )
        except Exception as e:
            _LOGGER.warning(f"Error processing discovery response from {host}: {e}")

async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the FlashForge integration."""
    _LOGGER.debug("Setting up FlashForge Adventurer integration")
    hass.data.setdefault(DOMAIN, {})

    # Start the active discovery task
    hass.loop.create_task(start_active_discovery(hass))
    
    return True

async def start_active_discovery(hass: core.HomeAssistant):
    """Periodically send out discovery packets and listen for responses."""
    _LOGGER.info("Starting Flashforge active UDP discovery")
    
    loop = asyncio.get_running_loop()
    
    while True:
        transport = None
        try:
             # Find local IP to bind to
            local_ip = socket.gethostbyname(socket.gethostname())
            
            # Create a socket for sending/receiving
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setblocking(False)
            
            # Allow multiple sockets to use the same port number (useful for dev/restarts)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                pass # SO_REUSEPORT not available on all OS (e.g. Windows)
                
            sock.bind((local_ip, DISCOVERY_PORT))

            transport, protocol = await loop.create_datagram_endpoint(
                lambda: FlashforgeDiscoveryProtocol(hass),
                sock=sock
            )

            # Construct the discovery packet based on your python script
            ip_parts = UDP_IP.split('.')
            m_search = (
                int(ip_parts[0]).to_bytes(1, 'big') + 
                int(ip_parts[1]).to_bytes(1, 'big') + 
                int(ip_parts[2]).to_bytes(1, 'big') + 
                int(ip_parts[3]).to_bytes(1, 'big') + 
                int(DISCOVERY_PORT).to_bytes(2, 'big') + 
                int(0).to_bytes(2, 'big')
            )

            _LOGGER.debug(f"Sending Flashforge discovery packet to {UDP_IP}:{UDP_PORT}")
            transport.sendto(m_search, (UDP_IP, UDP_PORT))

            # Leave the listener open for a short time to catch responses
            await asyncio.sleep(10)
            
        except Exception as e:
            _LOGGER.error(f"Error during Flashforge discovery: {e}")
        finally:
            if transport:
                transport.close()
                
        # Wait before next discovery cycle
        await asyncio.sleep(DISCOVERY_INTERVAL)

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    _LOGGER.warning(f"Setting up entry for {entry.title}")
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
    _LOGGER.warning("async_setup")
    hass.data.setdefault(DOMAIN, {})

    # 1. Start the UDP Listener Task
    _LOGGER.warning("Starting UDP Listener2")
    hass.loop.create_task(flashforge_discovery(hass))
    
    return True


