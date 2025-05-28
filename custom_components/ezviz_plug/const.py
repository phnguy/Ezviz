"""Constants for the ezviz integration."""

DOMAIN = "ezviz_plug"

# Configuration
CONF_SESSION_ID = "session_id"
CONF_RFSESSION_ID = "rf_session_id"

# Defaults
EU_URL = "apiieu.ezvizlife.com"
RUSSIA_URL = "apirus.ezvizru.com"
DEFAULT_TIMEOUT = 30

# Doorbell-specific constants
DOORBELL_ALARM_TYPE = "3"  # Doorbell event type in API
DOORBELL_DEFAULT_PAGE_SIZE = 20
DOORBELL_MAX_HISTORY_DAYS = 30
