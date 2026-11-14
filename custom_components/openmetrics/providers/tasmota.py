"""Tasmota metrics provider."""

import re
from datetime import datetime
from time import time
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    METRIC_CURRENT_AMPERES,
    METRIC_DEVICE_NAME,
    METRIC_ENERGY_DAILY_KWH,
    METRIC_ENERGY_TOTAL_KWH,
    METRIC_POWER_WATTS,
    METRIC_RELAY_STATE,
    METRIC_UPTIME_SECONDS,
    METRIC_VOLTAGE_VOLTS,
    METRIC_WIFI_SIGNAL_DBM,
    PROPERTY_LAST_START_TIME,
    PROPERTY_WIFI_BSSID,
    PROPERTY_WIFI_SSID,
    PROVIDER_NAME_TASMOTA,
    RESOURCE_TYPE_NODE,
)
from ..lib.metrics_core import Metric
from ..lib.samples import Sample
from ..metrics import MetricFilter
from ..metrics.data import ProviderInfoData, ResourceInfoData
from .base import MetricsProvider

# Metrics
TASMOTA_INFO = "tasmota_info"
TASMOTA_UPTIME_SECONDS = "tasmota_uptime_seconds"
TASMOTA_WIFI_STATION_INFO = "tasmota_wifi_station_info"
TASMOTA_WIFI_STATION_SIGNAL_DBM = "tasmota_wifi_station_signal_dbm"
TASMOTA_ENERGY_VOLTAGE_VOLTS = "tasmota_energy_voltage_volts"
TASMOTA_ENERGY_CURRENT_AMPERES = "tasmota_energy_current_amperes"
TASMOTA_ENERGY_POWER_ACTIVE_WATTS = "tasmota_energy_power_active_watts"
TASMOTA_ENERGY_POWER_KILOWATTS_DAILY = "tasmota_energy_power_kilowatts_daily"
TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL = "tasmota_energy_power_kilowatts"

# Regex
TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX = ".+"
TASMOTA_RELAY_STATE_REGEX = r"^tasmota_relay(\d+)_state$"
TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL_REGEX = (
    r"^tasmota_energy_power_kilowatts(?:_total)?$"
)

# Labels
TASMOTA_VERSION_LABEL = "version"
TASMOTA_IMAGE_LABEL = "image"
TASMOTA_DEVICE_NAME_LABEL = "devicename"
TASMOTA_BSSID_LABEL = "bssid"
TASMOTA_SSID_LABEL = "ssid"
TASMOTA_MAC_ADDRESS_LABEL = "mac_address"

PROVIDER_FILTERS = [
    MetricFilter(
        metric_key=TASMOTA_INFO,
        label_filters={
            TASMOTA_VERSION_LABEL: TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX,
            TASMOTA_DEVICE_NAME_LABEL: TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX,
        },
    ),
]


class TasmotaProvider(MetricsProvider):
    """Tasmota metrics provider."""

    metric_filters = [
        MetricFilter(metric_key=TASMOTA_UPTIME_SECONDS),
        MetricFilter(
            metric_key=TASMOTA_WIFI_STATION_INFO,
            label_filters={
                TASMOTA_BSSID_LABEL: TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX,
                TASMOTA_SSID_LABEL: TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX,
            },
        ),
        MetricFilter(
            metric_key=TASMOTA_WIFI_STATION_SIGNAL_DBM,
            label_filters={
                TASMOTA_MAC_ADDRESS_LABEL: TASMOTA_AT_LEAST_ONE_CHARACTER_REGEX,
            },
        ),
        MetricFilter(metric_key=TASMOTA_RELAY_STATE_REGEX),
        MetricFilter(metric_key=TASMOTA_ENERGY_VOLTAGE_VOLTS),
        MetricFilter(metric_key=TASMOTA_ENERGY_CURRENT_AMPERES),
        MetricFilter(metric_key=TASMOTA_ENERGY_POWER_ACTIVE_WATTS),
        MetricFilter(metric_key=TASMOTA_ENERGY_POWER_KILOWATTS_DAILY),
        MetricFilter(metric_key=TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL_REGEX),
    ]

    def __init__(self):
        """Initialize Tasmota provider."""
        super().__init__(PROVIDER_NAME_TASMOTA, RESOURCE_TYPE_NODE)
        self.provider_filters = PROVIDER_FILTERS

    def _get_or_create_resource(
        self, resources: dict, resource_name: str
    ) -> ResourceInfoData:
        """Get existing resource or create new one."""
        if resource_name not in resources:
            resources[resource_name] = ResourceInfoData(type=RESOURCE_TYPE_NODE)
        return resources[resource_name]

    def extract_provider_info(self, family: Metric, provider_info: ProviderInfoData):
        """Extract and store provider information."""
        if family.name == TASMOTA_INFO and family.samples:
            provider_info.version = family.samples[0].labels.get(TASMOTA_VERSION_LABEL)

    def extract_resource_info(self, family: Metric, resources: dict):
        """Extract and store Tasmota device resource information."""
        resource_info = self._get_or_create_resource(resources, self.RESOURCE_NAME)

        if family.name == TASMOTA_INFO:
            for sample in family.samples:
                devicename = sample.labels.get(TASMOTA_DEVICE_NAME_LABEL)
                if devicename:
                    resource_info.name = devicename
                    self.resource_name = devicename
                resource_info.software = PROVIDER_NAME_TASMOTA
                if sample.labels.get(TASMOTA_VERSION_LABEL):
                    resource_info.version = sample.labels[TASMOTA_VERSION_LABEL]
                if sample.labels.get(TASMOTA_IMAGE_LABEL):
                    resource_info.model = sample.labels[TASMOTA_IMAGE_LABEL]
        elif family.name == TASMOTA_WIFI_STATION_SIGNAL_DBM:
            for sample in family.samples:
                mac = sample.labels.get(TASMOTA_MAC_ADDRESS_LABEL)
                if mac:
                    resource_info.serial_number = mac
        else:
            match = re.match(TASMOTA_RELAY_STATE_REGEX, family.name)
            if match:
                relay_index = match.group(1)
                if not resource_info.relays:
                    resource_info.relays = set()
                resource_info.relays.add(relay_index)

    def collect_supported_metric(self, family: Metric, available_metrics: list[str]):
        """Collect supported metrics."""
        if family.name == TASMOTA_UPTIME_SECONDS:
            self._add_str_to_list_uniquely(METRIC_UPTIME_SECONDS, available_metrics)
        elif family.name == TASMOTA_WIFI_STATION_SIGNAL_DBM:
            self._add_str_to_list_uniquely(METRIC_WIFI_SIGNAL_DBM, available_metrics)
        elif re.match(TASMOTA_RELAY_STATE_REGEX, family.name):
            self._add_str_to_list_uniquely(METRIC_RELAY_STATE, available_metrics)
        elif family.name == TASMOTA_ENERGY_VOLTAGE_VOLTS:
            self._add_str_to_list_uniquely(METRIC_VOLTAGE_VOLTS, available_metrics)
        elif family.name == TASMOTA_ENERGY_CURRENT_AMPERES:
            self._add_str_to_list_uniquely(METRIC_CURRENT_AMPERES, available_metrics)
        elif family.name == TASMOTA_ENERGY_POWER_ACTIVE_WATTS:
            self._add_str_to_list_uniquely(METRIC_POWER_WATTS, available_metrics)
        elif family.name == TASMOTA_ENERGY_POWER_KILOWATTS_DAILY:
            self._add_str_to_list_uniquely(METRIC_ENERGY_DAILY_KWH, available_metrics)
        elif re.match(TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL_REGEX, family.name):
            self._add_str_to_list_uniquely(METRIC_ENERGY_TOTAL_KWH, available_metrics)

        # Add device name metric
        self._add_str_to_list_uniquely(METRIC_DEVICE_NAME, available_metrics)

    def prepare_metric_value(self, metric_key: str, sample: Sample) -> float | dict:
        """Override: Collect metric value."""
        if metric_key == TASMOTA_WIFI_STATION_INFO:
            return {
                TASMOTA_SSID_LABEL: sample.labels.get(TASMOTA_SSID_LABEL),
                TASMOTA_BSSID_LABEL: sample.labels.get(TASMOTA_BSSID_LABEL),
            }
        return sample.value

    def _pre_process_metrics(self, metrics: dict):
        """Pre-process metrics."""

    def _calculate_cpu_usage(
        self, resource: str, metrics: dict, update_interval: int
    ) -> dict[str, Any]:
        """Calculate CPU usage (not applicable for Tasmota)."""
        return {}

    def _calculate_memory_usage(self, resource: str, metrics: dict) -> dict[str, Any]:
        """Calculate memory usage (not applicable for Tasmota)."""
        return {}

    def _calculate_disk_usage(self, resource: str, metrics: dict) -> dict[str, Any]:
        """Calculate disk usage (not applicable for Tasmota)."""
        return {}

    def _calculate_network_io(
        self, resource: str, metrics: dict, update_interval: int
    ) -> dict[str, Any]:
        """Calculate network IO (not applicable for Tasmota)."""
        return {}

    def _calculate_uptime(self, resource: str, metrics: dict) -> dict[str, Any]:
        """Calculate uptime."""
        sensor_metrics = {}
        if not metrics:
            return sensor_metrics
        if TASMOTA_UPTIME_SECONDS in metrics:
            uptime_seconds = int(metrics[TASMOTA_UPTIME_SECONDS])
            sensor_metrics[METRIC_UPTIME_SECONDS] = uptime_seconds
            sensor_metrics[PROPERTY_LAST_START_TIME] = datetime.fromtimestamp(
                time() - float(uptime_seconds), dt_util.UTC
            )
        return sensor_metrics

    def _calculate_resource_metrics(
        self, resource: str, metrics: dict, update_interval: int
    ) -> dict | None:
        """Process resource metrics and return sensor metrics."""
        sensor_metrics = self._calculate_uptime(resource, metrics)
        if not metrics:
            return sensor_metrics

        # WiFi signal and station info
        if TASMOTA_WIFI_STATION_SIGNAL_DBM in metrics:
            sensor_metrics[METRIC_WIFI_SIGNAL_DBM] = metrics[
                TASMOTA_WIFI_STATION_SIGNAL_DBM
            ]
        if TASMOTA_WIFI_STATION_INFO in metrics and isinstance(
            metrics[TASMOTA_WIFI_STATION_INFO], dict
        ):
            sensor_metrics[PROPERTY_WIFI_SSID] = metrics[TASMOTA_WIFI_STATION_INFO].get(
                TASMOTA_SSID_LABEL
            )
            sensor_metrics[PROPERTY_WIFI_BSSID] = metrics[
                TASMOTA_WIFI_STATION_INFO
            ].get(TASMOTA_BSSID_LABEL)

        # Energy and electrical metrics
        if TASMOTA_ENERGY_VOLTAGE_VOLTS in metrics:
            sensor_metrics[METRIC_VOLTAGE_VOLTS] = metrics[TASMOTA_ENERGY_VOLTAGE_VOLTS]
        if TASMOTA_ENERGY_CURRENT_AMPERES in metrics:
            sensor_metrics[METRIC_CURRENT_AMPERES] = metrics[
                TASMOTA_ENERGY_CURRENT_AMPERES
            ]
        if TASMOTA_ENERGY_POWER_ACTIVE_WATTS in metrics:
            sensor_metrics[METRIC_POWER_WATTS] = metrics[
                TASMOTA_ENERGY_POWER_ACTIVE_WATTS
            ]
        if TASMOTA_ENERGY_POWER_KILOWATTS_DAILY in metrics:
            sensor_metrics[METRIC_ENERGY_DAILY_KWH] = metrics[
                TASMOTA_ENERGY_POWER_KILOWATTS_DAILY
            ]
        if TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL in metrics:
            sensor_metrics[METRIC_ENERGY_TOTAL_KWH] = metrics[
                TASMOTA_ENERGY_POWER_KILOWATTS_TOTAL
            ]

        # Relay state metrics
        for metric_key, metric_value in metrics.items():
            match = re.match(TASMOTA_RELAY_STATE_REGEX, metric_key)
            if match:
                relay_index = match.group(1)
                sensor_metrics[f"{METRIC_RELAY_STATE}_{relay_index}"] = int(
                    metric_value
                )

        return sensor_metrics
