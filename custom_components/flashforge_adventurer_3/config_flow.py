from homeassistant import config_entries
from typing import Any, Dict, Optional
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_TYPE, CONF_HOST
from homeassistant.helpers import selector
from homeassistant.config_entries import SOURCE_DISCOVERY

from .const import CONF_PRINTERS, DEFAULT_PORT, DOMAIN


CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


class GithubCustomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                self.data[CONF_PRINTERS] = []
                # Return the form of the next step.
                return self.async_create_entry(title='FlashForge Adventurer', data=self.data)
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

class FlashForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]
    
    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user or by custom discovery."""
        
        # If the flow was initiated by the custom listener
        if self.context.get("source") == SOURCE_DISCOVERY:
            # Go directly to the confirmation step with the discovered host
            # The discovered host is passed in via data={CONF_HOST: host}
            self.discovery_info = {CONF_HOST: user_input[CONF_HOST]}
            return await self.async_step_discovery_confirm()
        
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                self.data[CONF_PRINTERS] = []
                # Return the form of the next step.
                return self.async_create_entry(title='FlashForge Adventurer', data=self.data)
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_discovery(self, user_input: dict):
        """Handle a discovery step (initiated by the __init__.py listener)."""
        
        host = user_input[CONF_HOST]
        
        # 1. Set Unique ID (check if the device is already configured)
        # You'll likely need a follow-up API call to the printer to get a serial number
        # For now, use the host and port as a unique ID
        unique_id = f"{host}_{DISCOVERY_PORT}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        
        # 2. Confirm discovery
        self.context["title_placeholders"] = {"name": f"Adventurer 3 ({host})"}
        self.discovery_info = {CONF_HOST: host}
        
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Confirm the discovered device."""
        host = self.discovery_info[CONF_HOST]
        
        if user_input is not None:
            # User confirmed, create the entry
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={CONF_HOST: host},
            )

        # Show the confirmation form
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": host},
        )
