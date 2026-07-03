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
    PERCENTAGE,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_DURATION = timedelta(seconds=30)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up System Exporter sensors based on a config entry."""
    config = entry.data
    host = config[CONF_HOST]
    url = f"{host}/api/system"
    
    coordinator = SystemExporterDataCoordinator(hass, url)
    await coordinator.async_update()
    
    sensors = [
        SystemExporterSensor(coordinator, "cpu_load", "CPU Load", PERCENTAGE, "mdi:cpu-64-bit", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "cpu_temp_c", "CPU Temperature", "°C", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "ram_available_mb", "RAM Available", "MB", "mdi:memory", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "uptime", "Uptime", None, "mdi:clock-start", SensorDeviceClass.TIMESTAMP, None, entry.entry_id),
        SystemExporterSensor(coordinator, "load_1m", "Load (1m)", None, "mdi:speedometer-slow", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "load_5m", "Load (5m)", None, "mdi:speedometer-medium", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "load_15m", "Load (15m)", None, "mdi:speedometer", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "disk_usage_percent", "Disk Usage", PERCENTAGE, "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "network_rx_mbps", "Network RX Speed", "MB/s", "mdi:download-network", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "network_tx_mbps", "Network TX Speed", "MB/s", "mdi:upload-network", None, SensorStateClass.MEASUREMENT, entry.entry_id),
        SystemExporterSensor(coordinator, "rpi_undervoltage", "RPi Under-voltage", None, "mdi:flash", None, None, entry.entry_id),
        SystemExporterSensor(coordinator, "rpi_throttled", "RPi Throttled", None, "mdi:speedometer-slow", None, None, entry.entry_id),
    ]
    
    async_add_entities(sensors, True)
    
    # Schedule updates
    async def update_sensors(now):
        await coordinator.async_update()
        for sensor in sensors:
            sensor.async_write_ha_state()
            
    async_track_time_interval(hass, update_sensors, SCAN_INTERVAL_DURATION)


class SystemExporterDataCoordinator:
    """Coordinator to fetch data from the Go System Exporter API."""

    def __init__(self, hass, url):
        self.hass = hass
        self.url = url
        self.data = {}

    async def async_update(self):
        """Fetch data from the REST API."""
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.url) as response:
                        if response.status == 200:
                            self.data = await response.json()
                        else:
                            _LOGGER.warning("Error fetching data from %s: %s", self.url, response.status)
        except Exception as err:
            _LOGGER.warning("Failed to connect to System Exporter at %s: %s", self.url, err)


class SystemExporterSensor(SensorEntity):
    """Representation of a System Exporter sensor."""

    def __init__(self, coordinator, key, name, unit, icon, device_class, state_class, entry_id):
        self.coordinator = coordinator
        self._key = key
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class
        self._entry_id = entry_id

    @property
    def name(self):
        return f"System {self._name}"

    @property
    def unique_id(self):
        return f"{self._entry_id}_{self._key}"

    @property
    def state(self):
        val = self.coordinator.data.get(self._key)
        if val is None or val == "unavailable":
            return None
        return val

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        return self._state_class
