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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

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
    
    coordinator = SystemExporterDataCoordinator(hass, url)
    await coordinator.async_update()
    
    sensors = [
        SystemExporterSensor(coordinator, "cpu_load", "CPU Load", PERCENTAGE, "mdi:cpu-64-bit", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "cpu_temp_c", "CPU Temperature", "°C", "mdi:thermometer", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "ram_available_mb", "RAM Available", "MB", "mdi:memory", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "ram_total_mb", "RAM Total", "MB", "mdi:memory", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "uptime", "Uptime", None, "mdi:clock-start", SensorDeviceClass.TIMESTAMP, None, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_1m", "Load (1m)", None, "mdi:speedometer-slow", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_5m", "Load (5m)", None, "mdi:speedometer-medium", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "load_15m", "Load (15m)", None, "mdi:speedometer", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "disk_usage_percent", "Disk Usage", PERCENTAGE, "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "disk_total_gb", "Disk Total Size", "GB", "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_rx_total_mb", "Network RX Total", "MB", "mdi:download-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_tx_total_mb", "Network TX Total", "MB", "mdi:upload-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_undervoltage", "RPi Under-voltage", None, "mdi:flash", None, None, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled", "RPi Throttled", None, "mdi:speedometer-slow", None, None, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_undervoltage_has_occurred", "RPi Under-voltage Occurred", None, "mdi:flash-alert", None, None, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled_has_occurred", "RPi Throttled Occurred", None, "mdi:speedometer-slow", None, None, entry.entry_id, entry_name),
    ]
    
    async_add_entities(sensors, True)
    
    # Schedule updates
    async def update_sensors(now):
        await coordinator.async_update()
        for sensor in sensors:
            sensor.async_write_ha_state()
            
    async_track_time_interval(hass, update_sensors, scan_interval_duration)


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
                            self.data = {}
        except Exception as err:
            _LOGGER.warning("Failed to connect to System Exporter at %s: %s", self.url, err)
            self.data = {}


class SystemExporterSensor(SensorEntity):
    """Representation of a System Exporter sensor."""

    def __init__(self, coordinator, key, name, unit, icon, device_class, state_class, entry_id, entry_name):
        self.coordinator = coordinator
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
        return f"{self._entry_name} {self._name}"

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
