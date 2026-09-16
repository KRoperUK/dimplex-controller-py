"""Constants for Dimplex Controller."""

HTTP_OK = 200

# API Endpoints
BASE_URL = "https://mobileapi.gdhv-iot.com/api"
AUTH_URL = "https://gdhvb2c.b2clogin.com/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0"

# Headers
HEADER_USER_AGENT = "Dimplex Control/79810 CFNetwork/3860.300.31 Darwin/25.2.0"
HEADER_APP_NAME = "DimplexControl"
HEADER_APP_VERSION = "2.21.0"
HEADER_DEVICE_OS = "iOS"
HEADER_DEVICE_VERSION = "26.2.1"
HEADER_DEVICE_MANUFACTURER = "Apple"
HEADER_DEVICE_MODEL = "iPhone18,1"

# Auth
CLIENT_ID = "6c983ca3-506e-4933-8993-0e18e6a24bbd"
SCOPE = "https://gdhvb2c.onmicrosoft.com/Mobile/read offline_access openid profile"
REDIRECT_URI = "msal6c983ca3-506e-4933-8993-0e18e6a24bbd://auth/"
B2C_POLICY = "B2C_1A_DimplexControlSignupSignin"

# --- Temperature semantics ------------------------------------------------
# Values below come from the official app's own pickers and control paths, as
# recovered from Dimplex Control APK 2.26.0.
# See ``docs/decompiled-api-reference.md``.

# The mode carousels (Boost / Frost / Manual / Eco) offer 7–30 °C. Away shares
# the floor but *not* the ceiling — see AWAY_TEMP_MAX below.
MODE_TEMP_MIN = 7.0
MODE_TEMP_MAX = 30.0

# Away has its own, narrower ceiling. The app's Away picker will not offer above
# 18 °C, and a live test against a Quantum requesting 25 °C produced 18 °C in the
# cloud overview, the app and the appliance's own panel — so the earlier reading
# of ``UpdateTempRange`` that folded Away into the shared 7–30 carousel was
# over-generalised (dimplex-controller-py#98).
AWAY_TEMP_MIN = 7.0
AWAY_TEMP_MAX = 18.0

# Frost protection is always driven at the anti-freeze floor.
FROST_TEMPERATURE = 7.0

# Away defaults to the frost floor (it is an anti-freeze setback by default)
# but is user-settable across AWAY_TEMP_MIN..AWAY_TEMP_MAX.
DEFAULT_AWAY_TEMPERATURE = FROST_TEMPERATURE

# Boost's default in the app's picker.
DEFAULT_BOOST_TEMPERATURE = 21.0

# ``0xFF`` means "no explicit setpoint — follow the schedule". The cloud both
# reports this in ``ActiveSetPointTemperature`` when idle *and* expects it as
# the Advance temperature for Quantum / Storage Heater models with no setback.
NO_SETPOINT_SENTINEL = 255

# .NET ``default(DateTime)`` — how the cloud represents "unset" datetimes.
NULL_DATETIME = "0001-01-01T00:00:00"
