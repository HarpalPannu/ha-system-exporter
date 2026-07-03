import logging
import voluptuous as vol
import aiohttp
import async_timeout

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback

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
            name = user_input[CONF_NAME]
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, 30)
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
                                    title=name,
                                    data={
                                        CONF_HOST: host,
                                        CONF_NAME: name,
                                        CONF_SCAN_INTERVAL: scan_interval,
                                    },
                                )
                            errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        # Default UI schema
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="System Exporter"): str,
                vol.Required(CONF_HOST, default="http://localhost:8080"): str,
                vol.Required(CONF_SCAN_INTERVAL, default=30): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SystemExporterOptionsFlowHandler(config_entry)


class SystemExporterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for System Exporter."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].rstrip("/")
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            if not host.startswith("http://") and not host.startswith("https://"):
                host = f"http://{host}"

            url = f"{host}/api/system"

            # Validate the new URL
            try:
                async with async_timeout.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                await response.json()
                                return self.async_create_entry(
                                    title="",
                                    data={
                                        CONF_HOST: host,
                                        CONF_SCAN_INTERVAL: scan_interval,
                                    },
                                )
                            errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        current_host = self._config_entry.options.get(
            CONF_HOST, self._config_entry.data.get(CONF_HOST, "http://localhost:8080")
        )
        current_scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, self._config_entry.data.get(CONF_SCAN_INTERVAL, 30)
        )
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                    vol.Required(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            errors=errors,
        )
