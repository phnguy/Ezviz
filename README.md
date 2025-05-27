# EZVIZ Device Control

A Home Assistant custom integration for EZVIZ devices with switchable features. This integration allows you to control your EZVIZ devices like smart plugs, interphones, and gate controls from within Home Assistant.

## Features

- Control EZVIZ devices with switchable features (turn on/off)
- Monitor availability status
- Auto-discovery of all EZVIZ switchable devices in your account
- Integration with Home Assistant UI

## Supported Devices

### Smart Plugs
- CS-T30-10A-EU
- CS-T30-10B-EU
- CS-CPD7-R105-1K3
- And other EZVIZ smart plug models

### Security Devices
- Doorbell cameras with switchable features
- Interphones and gate controls
- Security cameras with switchable lights/alarms

### Other EZVIZ Devices
- Any EZVIZ device that has switchable features in the EZVIZ app
- Devices with multiple switchable functions are supported

## Prerequisites

- An EZVIZ account with registered devices
- Home Assistant installation (version 2021.12.0 or higher recommended)
- PyEzviz Python package (installed automatically)

## Installation

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Go to HACS → Integrations → Click the three dots in the top right corner → Custom repositories
3. Add this repository URL: `https://github.com/phnguy/Ezviz`
4. Select "Integration" as the category
5. Click "Add"
6. Search for "EZVIZ Device Control" in the Integrations tab
7. Click "Install"
8. Restart Home Assistant

### Option 2: Manual Installation

1. Download the latest release from the GitHub repository
2. Unzip the downloaded file
3. Copy the `custom_components/ezviz_plug` folder to your Home Assistant's `custom_components` directory
4. Restart Home Assistant

## Configuration

### Using the UI (Recommended)

1. Go to Settings → Devices & Services → Add Integration
2. Search for "EZVIZ Device Control"
3. Click on it and follow the configuration flow
4. Enter your EZVIZ account email and password
5. Select your region (EU, Russia, or Custom)
6. Click "Submit"

### Configuration Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| Email     | Yes      | Your EZVIZ account email |
| Password  | Yes      | Your EZVIZ account password |
| Region    | Yes      | Your EZVIZ server region (EU, Russia, or Custom) |

## Troubleshooting

### Common Issues

- **Cannot connect**: Make sure your EZVIZ account credentials are correct and your internet connection is stable.
- **MFA Required**: The integration currently doesn't support accounts with Multi-Factor Authentication enabled.
- **Devices not showing up**: Make sure your devices are properly registered in the EZVIZ app and are online.

### Logs

To get more detailed logs for troubleshooting, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.ezviz_plug: debug
    pyezviz: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
