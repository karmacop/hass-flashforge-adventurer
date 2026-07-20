import asyncio
import socket
from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN

#from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

import re

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
            response = data.decode('utf-8', errors='ignore')
            _LOGGER.debug(f"Flashforge discovery response from {host}")
            
            # The packet is padded with null bytes (\x00).
            parts = [part for part in response.split('\x00') if part]
            
            if not parts:
                return
                
            # The first non-empty part is the model name
            model_name = parts[0].strip()
            
            # The serial number (SN...) is the next significant string block
            serial_number = None
            for part in parts[1:]:
                # Look for the SN prefix within the remaining parts
                sn_match = re.search(r'(SN[A-Z0-9]+)', part)
                if sn_match:
                    serial_number = sn_match.group(1)
                    break
                    
            if not serial_number:
                _LOGGER.debug(f"Could not find Serial Number in response from {host}")

            _LOGGER.info(f"Discovered Flashforge: Model '{model_name}', SN '{serial_number}' at {host}")

            # Trigger the config flow discovery step
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "discovery"},
                    data={
                        "host": host, 
                        "serial": serial_number, 
                        "model": model_name
                    }
                )
            )
        except Exception as e:
            _LOGGER.warning(f"Error processing discovery response from {host}: {e}")

async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    # Set up the FlashForge integration.
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
            local_ip = "0.0.0.0"
            
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
    # Set up platform from a ConfigEntry.
    hass_data = dict(entry.data)
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
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
    # Handle options update.
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    # Unload a config entry.
    unload_ok = all(
        await asyncio.gather(
            hass.config_entries.async_forward_entry_unload(entry, 'sensor'),
            hass.config_entries.async_forward_entry_unload(entry, 'camera'),
        )
    )
    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]['unsub_options_update_listener']()

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
