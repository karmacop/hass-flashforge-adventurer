from homeassistant import config_entries
from typing import Any, Dict, Optional
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_TYPE, CONF_HOST
from homeassistant.helpers import selector
from homeassistant.config_entries import SOURCE_DISCOVERY

from .const import CONF_PRINTERS, DEFAULT_PORT, DOMAIN

import logging

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

_LOGGER = logging.getLogger(__name__)


class FlashForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        # Initialize the config flow.
        self.discovery_ip = None
    
    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        _LOGGER.warning(f'step user')
        # Handle a flow initiated by the user or by custom discovery.
        
        # Invoked when a user initiates a flow via the user interface.
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not errors:
                return self.async_create_entry(
                    title=f"FlashForge Adventurer ({user_input[CONF_IP_ADDRESS]})", 
                    data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_discovery(self, user_input: dict):
        # Handle a discovery step (initiated by the __init__.py listener).
        _LOGGER.warning(f'step discovery')
        host = discovery_info.get("host")
        if not host:
            return self.async_abort(reason="no_host_provided")
        
        # 1. Set Unique ID (check if the device is already configured)
        # You'll likely need a follow-up API call to the printer to get a serial number
        # For now, use the host and port as a unique ID
        await self.async_set_unique_id(host)
        
        # This will abort the flow if an entry with this unique_id already exists
        self._abort_if_unique_id_configured()

        self.discovery_ip = host
        
        # Set placeholders so the UI can show the IP being discovered
        self.context["title_placeholders"] = {"host": host}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        _LOGGER.warning(f'step discovery confirm')
        # Confirm the discovered device.
        if user_input is not None:
            # User confirmed, create the entry
            return self.async_create_entry(
                title=f"FlashForge Adventurer ({self.discovery_ip})",
                data={
                    CONF_IP_ADDRESS: self.discovery_ip,
                    CONF_PORT: DEFAULT_PORT
                },
            )

        # Show a simple confirmation form without inputs
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self.discovery_ip},
        )

    async def flashforge_discovery(hass: HomeAssistant):
        _LOGGER.warning("flashforge_discovery")
        # We use a standard socket for custom UDP listening
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(5)
        sock.setblocking(False)
        
        # The printer may broadcast to a multicast address (e.g., 255.0.0.9)
        # or just to the broadcast address (255.255.255.255). We bind to the discovery port.

        
        local_ip = sock.gethostbyname(socket.gethostname())
        _LOGGER.warning(f"trying {local_ip} on port {DISCOVERY_PORT}")
        try:
            sock.bind(local_ip, DISCOVERY_PORT)
        except OSError as err:
            _LOGGER.error("Failed to bind UDP socket on port {DISCOVERY_PORT}: {err}")
            return

        _LOGGER.debug("Starting Flashforge UDP discovery listener on port {DISCOVERY_PORT}")

        try:
            data, addr = await hass.loop.sock_recvfrom(sock, 1024)
            host = addr[0]
            _LOGGER.warning(f"got response from {host}")

            # 2. Process the received data
            # The 'data' payload will be the custom Flashforge ID packet.
            if not data.startswith(b'Adventurer'): # Placeholder check
                _LOGGER.debug("Received unknown UDP data from {host}")
                # continue

            # 3. Initiate the Configuration Flow
            # The data passed to the config flow will be the discovered IP address.
            _LOGGER.info("Flashforge Adventurer discovered at {host}")
            

        except (socket.error, asyncio.TimeoutError) as err:
            _LOGGER.warning(f"Flashforge discovery error: {err}")
