import logging
from datetime import timedelta
import aiohttp
import async_timeout

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    PERCENTAGE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up System Exporter sensors based on a config entry."""
    host = entry.options.get(CONF_HOST, entry.data.get(CONF_HOST))
    url = f"{host}/api/system"
    entry_name = entry.title

    # Retrieve dynamic scan interval from config entry settings
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 30))
    scan_interval_duration = timedelta(seconds=scan_interval)

    # Use Home Assistant's shared aiohttp session
    session = async_get_clientsession(hass)
    
    # Initialize the robust DataUpdateCoordinator
    coordinator = SystemExporterDataCoordinator(hass, url, session, scan_interval_duration)

    # Fetch initial data so we have state when entities are added
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        SystemExporterSensor(coordinator, "cpu_load", "CPU Load", PERCENTAGE, "mdi:cpu-64-bit", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "cpu_temp_c", "CPU Temperature", "°C", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "ram_available_mb", "RAM Available", "MB", "mdi:memory", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "ram_total_mb", "RAM Total", "MB", "mdi:memory", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "uptime", "Uptime", None, "mdi:clock-start", SensorDeviceClass.TIMESTAMP, None, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_1m", "Load (1m)", None, "mdi:speedometer-slow", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_5m", "Load (5m)", None, "mdi:speedometer-medium", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_15m", "Load (15m)", None, "mdi:speedometer", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "disk_available_gb", "Disk Available", "GB", "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "disk_total_gb", "Disk Total Size", "GB", "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_rx_total_mb", "Network RX Total", "MB", "mdi:download-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_tx_total_mb", "Network TX Total", "MB", "mdi:upload-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
    ]

    # Dynamically add RPi sensors only if the API reports non-null RPi fields
    rpi_sensors_added = False
    if coordinator.data and coordinator.data.get("rpi_undervoltage") is not None:
        sensors.extend(_create_rpi_sensors(coordinator, entry.entry_id, entry_name))
        rpi_sensors_added = True

    async_add_entities(sensors, True)

    # Callback listener for dynamically adding RPi sensors if they appear late
    # (e.g. if the API was offline during the very first boot)
    def handle_coordinator_update() -> None:
        nonlocal rpi_sensors_added
        if not rpi_sensors_added and coordinator.data and coordinator.data.get("rpi_undervoltage") is not None:
            new_sensors = _create_rpi_sensors(coordinator, entry.entry_id, entry_name)
            async_add_entities(new_sensors, True)
            rpi_sensors_added = True

    coordinator.async_add_listener(handle_coordinator_update)


def _create_rpi_sensors(coordinator, entry_id, entry_name):
    """Create RPi-specific sensor entities."""
    return [
        SystemExporterSensor(coordinator, "rpi_undervoltage", "RPi Under-voltage", None, "mdi:flash", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled", "RPi Throttled", None, "mdi:speedometer-slow", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_undervoltage_has_occurred", "RPi Under-voltage Occurred", None, "mdi:flash-alert", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled_has_occurred", "RPi Throttled Occurred", None, "mdi:speedometer-slow", None, None, entry_id, entry_name),
    ]


class SystemExporterDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API securely and efficiently."""

    def __init__(self, hass, url, session, update_interval):
        """Initialize the data updater."""
        self.url = url
        self.session = session
        self._failed_attempts = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.get(self.url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    # Reset failure count on success
                    if self._failed_attempts > 0:
                        _LOGGER.info("Connection to System Exporter restored.")
                        self._failed_attempts = 0
                        
                    return data
        except Exception as err:
            self._failed_attempts += 1
            if self._failed_attempts <= 5:
                # Return last known data to tolerate transient drops
                _LOGGER.debug("Transient API drop (%s/5): %s", self._failed_attempts, err)
                if self.data:
                    return self.data
            
            # After 5 failures, actually raise the error which marks entities as Unavailable
            raise UpdateFailed(f"Error communicating with API: {err}")


class SystemExporterSensor(CoordinatorEntity, SensorEntity):
    """Native implementation of a System Exporter sensor using CoordinatorEntity."""

    def __init__(self, coordinator, key, name, unit, icon, device_class, state_class, entry_id, entry_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class
        self._entry_id = entry_id
        self._entry_name = entry_name

    @property
    def name(self):
        """Return the formatted name of the sensor."""
        return f"{self._entry_name} {self._name}"

    @property
    def unique_id(self):
        """Return a globally unique ID for the sensor."""
        return f"{self._entry_id}_{self._key}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._key)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self):
        """Return the state class."""
        return self._state_class

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._entry_name,
            manufacturer="Harpal",
            model="Go System Exporter",
            sw_version="1.0.0",
        )
