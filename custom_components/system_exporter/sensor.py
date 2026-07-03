import logging
from datetime import timedelta
import aiohttp

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

    # Use Home Assistant's shared aiohttp session (managed lifecycle, connection pooling)
    session = async_get_clientsession(hass)
    coordinator = SystemExporterDataCoordinator(hass, url, session)
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
        SystemExporterSensor(coordinator, "disk_available_gb", "Disk Available", "GB", "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "disk_total_gb", "Disk Total Size", "GB", "mdi:harddisk", None, SensorStateClass.MEASUREMENT, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_rx_total_mb", "Network RX Total", "MB", "mdi:download-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
        SystemExporterSensor(coordinator, "network_tx_total_mb", "Network TX Total", "MB", "mdi:upload-network", None, SensorStateClass.TOTAL_INCREASING, entry.entry_id, entry_name),
    ]

    # Only add RPi sensors if the API reports non-null values for RPi fields
    rpi_sensors_added = False
    if coordinator.data.get("rpi_undervoltage") is not None:
        sensors.extend(_create_rpi_sensors(coordinator, entry.entry_id, entry_name))
        rpi_sensors_added = True

    async_add_entities(sensors, True)

    # Schedule periodic updates
    async def update_sensors(now):
        nonlocal rpi_sensors_added
        await coordinator.async_update()

        # Dynamically add RPi sensors if they appear after boot
        # (handles case where API was slow to start when HA booted)
        if not rpi_sensors_added and coordinator.data.get("rpi_undervoltage") is not None:
            rpi_list = _create_rpi_sensors(coordinator, entry.entry_id, entry_name)
            async_add_entities(rpi_list, True)
            sensors.extend(rpi_list)
            rpi_sensors_added = True

        for sensor in sensors:
            sensor.async_write_ha_state()

    # Store the unsub callback and register it for cleanup on entry unload
    unsub = async_track_time_interval(hass, update_sensors, scan_interval_duration)
    entry.async_on_unload(unsub)


def _create_rpi_sensors(coordinator, entry_id, entry_name):
    """Create RPi-specific sensor entities."""
    return [
        SystemExporterSensor(coordinator, "rpi_undervoltage", "RPi Under-voltage", None, "mdi:flash", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled", "RPi Throttled", None, "mdi:speedometer-slow", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_undervoltage_has_occurred", "RPi Under-voltage Occurred", None, "mdi:flash-alert", None, None, entry_id, entry_name),
        SystemExporterSensor(coordinator, "rpi_throttled_has_occurred", "RPi Throttled Occurred", None, "mdi:speedometer-slow", None, None, entry_id, entry_name),
    ]


class SystemExporterDataCoordinator:
    """Coordinator to fetch data from the Go System Exporter API."""

    def __init__(self, hass, url, session):
        self.hass = hass
        self.url = url
        self._session = session
        self.data = {}
        self.available = True
        self._failed_attempts = 0

    async def async_update(self):
        """Fetch data from the REST API using the shared HA session."""
        try:
            async with self._session.get(self.url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    self.data = await response.json()
                    self.available = True
                    self._failed_attempts = 0
                else:
                    _LOGGER.warning("Error fetching data from %s: %s", self.url, response.status)
                    self._handle_failure()
        except Exception as err:
            _LOGGER.warning("Failed to connect to System Exporter at %s: %s", self.url, err)
            self._handle_failure()

    def _handle_failure(self):
        """Handle fetch failure with a retry threshold before marking unavailable."""
        self._failed_attempts += 1
        if self._failed_attempts == 6:
            _LOGGER.warning(
                "Connection to System Exporter failed 5 times in a row. Marking entities as unavailable."
            )
            self.available = False


class SystemExporterSensor(SensorEntity):
    """Representation of a System Exporter sensor."""

    # Disable HA's built-in platform polling — we use async_track_time_interval instead
    should_poll = False

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
    def available(self):
        """Return True if the API server is reachable."""
        return self.coordinator.available

    @property
    def state(self):
        val = self.coordinator.data.get(self._key)
        if val is None:
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
