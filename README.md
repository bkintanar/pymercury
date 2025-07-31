# PyMercury - Mercury.co.nz Python Library

A comprehensive Python library for interacting with Mercury.co.nz services, including OAuth authentication and selfservice API integration.

## Features

- **OAuth 2.0 PKCE Authentication** - Secure authentication with Mercury.co.nz
- **Selfservice API Integration** - Access customer, account, and service data
- **Clean Architecture** - Modular design with separate OAuth and API clients
- **Type Safety** - Full type hints for better IDE support
- **Comprehensive Error Handling** - Detailed exceptions for different error scenarios
- **Flexible Configuration** - Environment variable support with sensible defaults

## Installation

```bash
pip install pymercury
```

## Quick Start

### Simple Authentication

```python
from pymercury import authenticate

# Get OAuth tokens
tokens = authenticate("your-email@example.com", "your-password")
print(f"Customer ID: {tokens.customer_id}")
print(f"Access Token: {tokens.access_token}")
```

### Complete Account Data

```python
from pymercury import get_complete_data

# Get everything in one call
data = get_complete_data("your-email@example.com", "your-password")

print(f"Customer ID: {data.customer_id}")
print(f"Account IDs: {data.account_ids}")
print(f"Electricity Services: {data.service_ids.electricity}")
print(f"Gas Services: {data.service_ids.gas}")
print(f"Broadband Services: {data.service_ids.broadband}")
```

### Main Client (Recommended)

```python
from pymercury import MercuryClient

# Create client and login
client = MercuryClient("your-email@example.com", "your-password")
client.login()

# Easy access to information
customer_id = client.customer_id
account_ids = client.account_ids
service_ids = client.service_ids

# Get complete data
complete_data = client.get_complete_account_data()
```

## Advanced Usage

### Separate OAuth and API Clients

```python
from pymercury.oauth import MercuryOAuthClient
from pymercury.api import MercuryAPIClient

# OAuth authentication only
oauth_client = MercuryOAuthClient("email@example.com", "password")
tokens = oauth_client.authenticate()

# API calls with existing tokens
api_client = MercuryAPIClient(tokens.access_token)
customer_info = api_client.get_customer_info(tokens.customer_id)
accounts = api_client.get_accounts(tokens.customer_id)
```

### Electricity Usage and Billing

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Get electricity meter information
meter_info = api_client.get_electricity_meter_info(customer_id, account_id)
if meter_info:
    print(f"Meter Number: {meter_info.meter_number}")
    print(f"Meter Type: {meter_info.meter_type}")

# Get bill summary
bill_summary = api_client.get_bill_summary(customer_id, account_id)
if bill_summary:
    print(f"Current Balance: ${bill_summary.current_balance}")
    print(f"Due Date: {bill_summary.due_date}")

# Get electricity usage (defaults to last 14 days)
electricity_usage = api_client.get_electricity_usage(customer_id, account_id, service_id)
if electricity_usage:
    print(f"Total Usage: {electricity_usage.total_usage} kWh")
    print(f"Average Daily Usage: {electricity_usage.average_daily_usage} kWh")
    print(f"Average Temperature: {electricity_usage.average_temperature}°C")
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# OAuth Configuration
MERCURY_CLIENT_ID=4c8c2c47-24cd-485d-aad9-12f3d95b3ceb
MERCURY_REDIRECT_URI=https://myaccount.mercury.co.nz
MERCURY_BASE_URL=https://login.mercury.co.nz/fc07dca7-cd6a-4578-952b-de7a7afaebdc
MERCURY_TIMEOUT=20

# API Configuration
MERCURY_API_BASE_URL=https://apis.mercury.co.nz/selfservice/v1
MERCURY_API_SUBSCRIPTION_KEY=f62040b20cf9401fb081880cb71c7dec
```

### Programmatic Configuration

```python
from pymercury import MercuryConfig, MercuryClient

config = MercuryConfig(
    client_id="your-client-id",
    api_subscription_key="your-api-key",
    timeout=30
)

client = MercuryClient("email@example.com", "password", config=config)
```

## Error Handling

```python
from pymercury import (
    MercuryClient,
    MercuryAuthenticationError,
    MercuryAPIError,
    MercuryError
)

try:
    client = MercuryClient("email@example.com", "password")
    client.login()
    data = client.get_complete_account_data()

except MercuryAuthenticationError:
    print("Invalid credentials")
except MercuryAPIError as e:
    print(f"API error: {e}")
except MercuryError as e:
    print(f"Mercury.co.nz error: {e}")
```

## API Methods

The library provides access to all Mercury.co.nz selfservice APIs:

- `get_customer_info()` - Customer information
- `get_accounts()` - Account details
- `get_services()` - Service information
- `get_electricity_meter_info()` - Meter details
- `get_bill_summary()` - Billing information
- `get_electricity_usage()` - Usage data with temperature
- `get_electricity_usage_hourly()` - Hourly usage data
- `get_electricity_usage_monthly()` - Monthly usage data
- `get_electricity_plans()` - Available plans and pricing
- `get_electricity_meter_reads()` - Meter reading history

## Requirements

- Python 3.7+
- `requests>=2.25.0`

## Development

For development, install with optional dependencies:

```bash
pip install pymercury[dev]
```

## Testing

Run the comprehensive test suite:

```bash
python test_mercury_library.py
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For support, please open an issue on the GitHub repository.
