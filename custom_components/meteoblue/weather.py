from datetime import timedelta
from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.const import UnitOfLength, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt

from .const import DOMAIN
from .coordinator import MeteoblueDataUpdateCoordinator

# https://docs.meteoblue.com/en/meteo/variables/pictograms
# https://www.home-assistant.io/integrations/weather/
HOURLY_PICTOCODE_CONDITION_MAP = {
    1: "sunny",                 # Clear, cloudless sky
    2: "sunny",                 # Clear, few cirrus
    3: "sunny",                 # Clear with cirrus
    4: "partlycloudy",          # Clear with few low clouds
    5: "partlycloudy",          # Clear with few low clouds and few cirrus
    6: "partlycloudy",          # Clear with few low clouds and cirrus
    7: "partlycloudy",          # Partly cloudy
    8: "partlycloudy",          # Partly cloudy and few cirrus
    9: "partlycloudy",          # Partly cloudy and cirrus
    10: "lightning",            # Mixed with some thunderstorm clouds possible
    11: "lightning",            # Mixed with few cirrus with some thunderstorm clouds possible
    12: "lightning",            # Mixed with cirrus with some thunderstorm clouds possible
    13: "fog",                  # Clear but hazy
    14: "fog",                  # Clear but hazy with few cirrus
    15: "fog",                  # Clear but hazy with cirrus
    16: "fog",                  # Fog/low stratus clouds
    17: "fog",                  # Fog/low stratus clouds with few cirrus
    18: "fog",                  # Fog/low stratus clouds with cirrus
    19: "cloudy",               # Mostly cloudy
    20: "cloudy",               # Mostly cloudy and few cirrus
    21: "cloudy",               # Mostly cloudy and cirrus
    22: "cloudy",               # Overcast
    23: "rainy",                # Overcast with rain
    24: "snowy",                # Overcast with snow
    25: "pouring",              # Overcast with heavy rain
    26: "snowy",                # Overcast with heavy snow
    27: "lightning-rainy",      # Rain, thunderstorms likely
    28: "lightning-rainy",      # Light rain, thunderstorms likely
    29: "snowy",                # Storm with heavy snow
    30: "lightning-rainy",      # Heavy rain, thunderstorms likely
    31: "snowy-rainy",          # Mixed with showers
    32: "snowy",                # Mixed with snow showers
    33: "rainy",                # Overcast with light rain
    34: "snowy",                # Overcast with light snow
    35: "snowy-rainy",          # Overcast with mixture of snow and rain
}

HOURLY_PICTOCODE_CONDITION_MAP_NIGHT = {
    1: "clear-night",
    2: "clear-night",
    3: "clear-night",
    4: "partlycloudy",
    5: "partlycloudy",
    6: "partlycloudy",
    7: "partlycloudy",
    8: "partlycloudy",
    9: "partlycloudy",
    10: "lightning",
    11: "lightning",
    12: "lightning",
    13: "fog",
    14: "fog",
    15: "fog",
    16: "fog",
    17: "fog",
    18: "fog",
    19: "cloudy",
    20: "cloudy",
    21: "cloudy",
    22: "cloudy",
    23: "rainy",
    24: "snowy",
    25: "pouring",
    26: "snowy",
    27: "lightning-rainy",
    28: "lightning-rainy",
    29: "snowy",
    30: "lightning-rainy",
    31: "snowy-rainy",
    32: "snowy",
    33: "rainy",
    34: "snowy",
    35: "snowy-rainy",
}

DAILY_PICTOCODE_CONDITION_MAP = {
    1: "sunny",
    2: "partlycloudy",
    3: "partlycloudy",
    4: "cloudy",
    5: "fog",
    6: "rainy",
    7: "rainy",
    8: "lightning-rainy",
    9: "snowy",
    10: "snowy",
    11: "snowy-rainy",
    12: "rainy",
    13: "snowy",
    14: "rainy",
    15: "snowy",
    16: "rainy",
    17: "snowy",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: MeteoblueDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MeteoblueWeather(coordinator, entry)])


class MeteoblueWeather(CoordinatorEntity, WeatherEntity):
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, coordinator: MeteoblueDataUpdateCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_name = entry.title
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Meteoblue",
            entry_type="service",
        )

    @property
    def condition(self):
        code = self.coordinator.data["data_1h"]["pictocode"][0]
        isdaylight = self.coordinator.data["data_1h"]["isdaylight"][0]
        return HOURLY_PICTOCODE_CONDITION_MAP.get(code, "unknown") if isdaylight else HOURLY_PICTOCODE_CONDITION_MAP_NIGHT.get(code, "unknown")

    @property
    def native_temperature(self):
        return self.coordinator.data["data_1h"]["temperature"][0]

    @property
    def native_pressure(self):
        return self.coordinator.data["data_1h"]["sealevelpressure"][0]

    @property
    def native_wind_speed(self):
        return self.coordinator.data["data_1h"]["windspeed"][0]

    @property
    def humidity(self):
        return self.coordinator.data["data_1h"]["relativehumidity"][0]

    def _build_forecast(self, data, *, daily, timezone = None):
        forecasts: list[Forecast] = []
        if daily:
            for time, t_max, t_min, code in zip(data["time"], data["temperature_max"], data["temperature_min"], data["pictocode"]):
                forecasts.append({"datetime": time, "native_temperature": t_max, "native_templow": t_min, "condition": DAILY_PICTOCODE_CONDITION_MAP.get(code, "unknown")})
        else:   
            tz = dt.get_time_zone(self.hass.config.time_zone)
            now_before_30min = dt.now(tz) - timedelta(minutes=30)
            for time, temp, code, isdaylight in zip(data["time"], data["temperature"], data["pictocode"], data["isdaylight"]):
                if dt.parse_datetime(time).replace(tzinfo=tz) < now_before_30min:
                    continue
                mapper = HOURLY_PICTOCODE_CONDITION_MAP if isdaylight else HOURLY_PICTOCODE_CONDITION_MAP_NIGHT
                forecasts.append({"datetime": time, "native_temperature": temp, "condition": mapper.get(code, "unknown")})
        return forecasts

    async def async_forecast_daily(self):
        return self._build_forecast(self.coordinator.data["data_day"], daily=True)

    async def async_forecast_hourly(self):
        tz_abbr = self.coordinator.data["metadata"].get("timezone_abbrevation", "")
        return self._build_forecast(self.coordinator.data["data_1h"], daily=False, timezone=dt.get_time_zone(tz_abbr))

