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
