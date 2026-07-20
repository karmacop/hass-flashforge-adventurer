from homeassistant import config_entries
import asyncio
import socket
import re
from typing import Any, Dict, Optional
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_TYPE, CONF_HOST
from homeassistant.helpers import selector

from .const import CONF_PRINTERS, DEFAULT_PORT, DOMAIN

import logging

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORT:int = 18001
DISCOVERY_TIMEOUT:int = 10
DISCOVERY_TIMEOUT_USER:int = 5
DISCOVERY_INTERVAL:int = 300
UDP_IP:str = "225.0.0.9"
UDP_PORT:int = 19000

class FlowDiscoveryProtocol(asyncio.DatagramProtocol):
    # Protocol to handle UDP discovery responses during the Config Flow.
    def __init__(self):
        self.found_printers = {}

    def datagram_received(self, data, addr):
        host = addr[0]
        try:
            response = data.decode('utf-8', errors='ignore')
            parts = [part for part in response.split('\x00') if part]
            
            if not parts:
                return
                
            model_name = parts[0].strip()
            
            serial_number = None
            for part in parts[1:]:
                sn_match = re.search(r'(SN[A-Z0-9]+)', part)
                if sn_match:
                    serial_number = sn_match.group(1)
                    break
                    
            self.found_printers[host] = {
                "model": model_name,
                "serial": serial_number
            }
        except Exception as e:
            _LOGGER.debug(f"Config flow discovery parsing error: {e}")

class FlashForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    discovery_ip: Optional[str] = None
    discovery_name: Optional[str] = None

    async def _async_discover_printers(self) -> dict:
        # Send a UDP broadcast and wait x seconds for replies.
        loop = asyncio.get_running_loop()
        protocol = FlowDiscoveryProtocol()
        transport = None
        try:
            local_ip = "0.0.0.0"
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setblocking(False)

            _LOGGER.warning(f'Flashforge A: {local_ip} : {sock}')
            
            # Allow reusing the port if the background listener in __init__.py is active
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                _LOGGER.warning(f'Flashforge A: attribute error')
                pass 
            
            sock.bind((local_ip, DISCOVERY_PORT))
            
            transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                sock=sock
            )
            
            ip_parts = UDP_IP.split('.')
            m_search = (
                int(ip_parts[0]).to_bytes(1, 'big') + 
                int(ip_parts[1]).to_bytes(1, 'big') + 
                int(ip_parts[2]).to_bytes(1, 'big') + 
                int(ip_parts[3]).to_bytes(1, 'big') + 
                int(DISCOVERY_PORT).to_bytes(2, 'big') + 
                int(0).to_bytes(2, 'big')
            )


            transport.sendto(m_search, (UDP_IP, UDP_PORT))
            
            # Show a loading spinner to the user for x seconds while waiting
            await asyncio.sleep(DISCOVERY_TIMEOUT_USER)
            
        except Exception as e:
            _LOGGER.error(f"Error during UI discovery: {e}")
        finally:
            if transport:
                transport.close()
        _LOGGER.warning(f'Flashforge B: {protocol}')
        return protocol.found_printers
    
    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        _LOGGER.warning(f'step user')
        # Handle a flow initiated by the user or by custom discovery.
        _LOGGER.debug('step user initiated - starting discovery scan')
        
        self.discovered_devices = await self._async_discover_printers()

        if self.discovered_devices:
            # Found devices, ask the user to pick one
            _LOGGER.warning(f'Found devices, ask the user to pick one user')
            return await self.async_step_pick_device()
        else:
            # No devices found, skip straight to manual entry
            return await self.async_step_manual()

    async def async_step_pick_device(self, user_input: Optional[Dict[str, Any]] = None):
        # Handle the device selection dropdown.
        if user_input is not None:
            selected = user_input.get("device")
            
            if selected == "manual":
                return await self.async_step_manual()
            
            # User selected a printer from the dropdown
            device_info = self.discovered_devices[selected]
            ip = selected
            serial = device_info.get("serial")
            model = device_info.get("model", "FlashForge Printer")
            
            unique_id = serial if serial else ip
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: ip})
            
            return self.async_create_entry(
                title=f"{model} ({ip})",
                data={
                    CONF_IP_ADDRESS: ip,
                    CONF_PORT: DEFAULT_PORT
                }
            )

        # Build options list for dropdown
        options = {
            ip: f"{data.get('model', 'Unknown Model')} ({ip})" 
            for ip, data in self.discovered_devices.items()
        }
        options["manual"] = "Enter IP Manually"
        
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(options)
            })
        )
    
    async def async_step_manual(self, user_input: Optional[Dict[str, Any]] = None):
        # Handle manual IP entry.
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not errors:
                return self.async_create_entry(
                    title=f"FlashForge ({user_input[CONF_IP_ADDRESS]})", 
                    data=user_input
                )
                
        return self.async_show_form(
            step_id="manual", data_schema=CONFIG_SCHEMA, errors=errors
        )
    
    async def async_step_discovery(self, discovery_info: dict):
        # Handle a discovery step (initiated by the __init__.py listener).
        _LOGGER.warning(f'step discovery')
        host = discovery_info.get("host")
        serial = discovery_info.get("serial")
        model = discovery_info.get("model", "FlashForge Printer")
        
        if not host:
            return self.async_abort(reason="no_host_provided")
        
        # Use the serial number as the unique ID if we have it, otherwise fallback to IP
        unique_id = serial if serial else host
        await self.async_set_unique_id(unique_id)
        
        # This will abort the flow if an entry with this unique_id already exists
        self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: host})

        self.discovery_ip = host
        self.discovery_name = f"{model} ({host})"
        
        # Set placeholders so the UI can show the IP being discovered
        self.context["title_placeholders"] = {"name": self.discovery_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        _LOGGER.warning(f'step discovery confirm')
        # Confirm the discovered device.
        if user_input is not None:
            # User confirmed, create the entry
            return self.async_create_entry(
                title=self.discovery_name or f"FlashForge ({self.discovery_ip})",
                data={
                    CONF_IP_ADDRESS: self.discovery_ip,
                    CONF_PORT: DEFAULT_PORT
                },
            )

        # Show a simple confirmation form without inputs
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self.discovery_name},
        )

    """async def flashforge_discovery(hass: HomeAssistant):
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
            _LOGGER.warning(f"Flashforge discovery error: {err}")"""
