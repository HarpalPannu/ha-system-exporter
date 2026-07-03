import logging
import voluptuous as vol
import aiohttp
import async_timeout

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class SystemExporterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for System Exporter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].rstrip("/")
            if not host.startswith("http://") and not host.startswith("https://"):
                host = f"http://{host}"

            url = f"{host}/api/system"
            
            # Test connectivity before saving configuration
            try:
                async with async_timeout.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                await response.json()
                                return self.async_create_entry(
                                    title=f"System Exporter ({user_input[CONF_HOST]})",
                                    data={CONF_HOST: host},
                                )
                            errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        # Default UI schema
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="http://localhost:8080"): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
