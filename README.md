# PyMercury - Mercury.co.nz Python Library

A comprehensive Python library for interacting with Mercury.co.nz services, including OAuth authentication and selfservice API integration.

## Features

- **OAuth 2.0 PKCE Authentication** - Secure authentication with Mercury.co.nz
- **Selfservice API Integration** - Access customer, account, and service data
- **Multi-Service Support** - Electricity and Gas service integration
- **Clean Architecture** - Modular design with separate OAuth and API clients
- **Type Safety** - Full type hints for better IDE support
- **Comprehensive Error Handling** - Detailed exceptions for different error scenarios
- **Flexible Configuration** - Environment variable support with sensible defaults

## Installation

```bash
pip install pymercury
```

### Development Installation

For development or to run the examples:

```bash
# Clone the repository
git clone <repository-url>
cd pymercury

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### Environment Setup (Recommended)

For security, use environment variables instead of hardcoding credentials:

1. **Create a `.env` file** in the project root:

   ```bash
   cp env.template .env
   ```

2. **Edit `.env` with your Mercury Energy credentials**:

   ```bash
   # Mercury Energy Credentials
   MERCURY_EMAIL=your-email@example.com
   MERCURY_PASSWORD=your-actual-password
   ```

3. **The library automatically loads these credentials**:
   ```python
   # No need to hardcode credentials!
   from pymercury import authenticate
   tokens = authenticate()  # Uses MERCURY_EMAIL and MERCURY_PASSWORD from .env
   ```

> **Security Note**: Never commit `.env` files to version control. The `.env` file is automatically ignored by git.

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
oauth_client = MercuryOAuthClient("your-email@example.com", "your-password")
tokens = oauth_client.authenticate()

# API calls with existing tokens
api_client = MercuryAPIClient(tokens.access_token)
customer_info = api_client.get_customer_info(tokens.customer_id)
accounts = api_client.get_accounts(tokens.customer_id)
```

## Electricity Services

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
```

### Electricity Usage Data

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Get electricity usage (defaults to last 14 days)
electricity_usage = api_client.get_electricity_usage(customer_id, account_id, service_id)
if electricity_usage:
    print(f"Total Usage: {electricity_usage.total_usage} kWh")
    print(f"Average Daily Usage: {electricity_usage.average_daily_usage} kWh")
    print(f"Average Temperature: {electricity_usage.average_temperature}°C")

# Get hourly electricity usage (2 days ending yesterday)
hourly_electricity = api_client.get_electricity_usage_hourly(customer_id, account_id, service_id)
if hourly_electricity:
    print(f"Hourly Usage Period: {hourly_electricity.start_date} to {hourly_electricity.end_date}")
    print(f"Total Hourly Usage: {hourly_electricity.total_usage} kWh")

# Get monthly electricity usage (1 year period)
monthly_electricity = api_client.get_electricity_usage_monthly(customer_id, account_id, service_id)
if monthly_electricity:
    print(f"Monthly Usage Period: {monthly_electricity.start_date} to {monthly_electricity.end_date}")
    print(f"Total Monthly Usage: {monthly_electricity.total_usage} kWh")

# Get electricity usage content (disclaimer, modal info, etc.)
electricity_content = api_client.get_electricity_usage_content()
if electricity_content:
    print(f"Usage content available for electricity service")
```

## Gas Services

### Gas Usage Content

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Get gas usage content (disclaimer, modal info, etc.)
gas_content = api_client.get_gas_usage_content()
if gas_content:
    print(f"Content Name: {gas_content.content_name}")           # "Gas/Usage"
    print(f"Locale: {gas_content.locale}")                       # "en"
    print(f"Usage Disclaimer: {gas_content.disclaimer_usage}")   # Gas billing info
    print(f"Modal Title: {gas_content.usage_info_modal_title}")  # "USAGE GRAPH KEY"
```

### Gas Usage Data

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Get gas usage data (defaults to last 14 days)
gas_usage = api_client.get_gas_usage(customer_id, account_id, service_id)
if gas_usage:
    print(f"Service Type: {gas_usage.service_type}")               # "Gas"
    print(f"Usage Period: {gas_usage.usage_period}")               # "Daily", "Monthly", etc.
    print(f"Total Usage: {gas_usage.total_usage} units")           # Gas consumption
    print(f"Total Cost: ${gas_usage.total_cost}")                  # Total cost
    print(f"Average Daily: {gas_usage.average_daily_usage} units") # Daily average
    print(f"Data Points: {gas_usage.data_points}")                 # Number of readings

# Get hourly gas usage (2 days ending yesterday)
hourly_gas = api_client.get_gas_usage_hourly(customer_id, account_id, service_id)
if hourly_gas:
    print(f"Hourly Usage Period: {hourly_gas.start_date} to {hourly_gas.end_date}")
    print(f"Total Hourly Usage: {hourly_gas.total_usage} units")

# Get monthly gas usage (1 year period)
monthly_gas = api_client.get_gas_usage_monthly(customer_id, account_id, service_id)
if monthly_gas:
    print(f"Monthly Usage Period: {monthly_gas.start_date} to {monthly_gas.end_date}")
    print(f"Total Monthly Usage: {monthly_gas.total_usage} units")
```

## Broadband Services

### Fibre Broadband Usage and Service Information

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Get broadband service information and usage data
broadband_info = api_client.get_broadband_usage(customer_id, account_id, service_id)
if broadband_info:
    # Service information
    print(f"Plan Name: {broadband_info.plan_name}")                 # "FibreClassic Unlimited Naked"
    print(f"Plan Code: {broadband_info.plan_code}")                 # "20398"
    print(f"Service Type: {broadband_info.service_type}")           # "Broadband"

    # Usage summary
    print(f"Total Data Used: {broadband_info.total_data_used} GB")  # Total usage
    print(f"Average Daily: {broadband_info.avg_daily_usage} GB")    # Daily average
    print(f"Max Daily: {broadband_info.max_daily_usage} GB")        # Peak usage day
    print(f"Usage Days: {broadband_info.usage_days}")               # Days with usage > 0
    print(f"Data Points: {broadband_info.data_points}")             # Total days of data

    # Usage period
    print(f"Period: {broadband_info.start_date} to {broadband_info.end_date}")

    # Daily usage breakdown (first 5 days)
    for day in broadband_info.daily_usages[:5]:
        date = day['date'][:10]  # Just the date part
        usage = day['usage']
        print(f"  {date}: {usage} GB")

# Alternative method (alias)
fibre_info = api_client.get_fibre_usage(customer_id, account_id, service_id)
```

### Generic Usage Methods

```python
from pymercury.api import MercuryAPIClient

# Initialize API client with access token
api_client = MercuryAPIClient(access_token)

# Generic usage content method (works for any service type)
electricity_content = api_client.get_usage_content("Electricity")
gas_content = api_client.get_usage_content("Gas")

# Generic usage data method (works for any service type)
electricity_usage = api_client.get_service_usage(customer_id, account_id, 'electricity', service_id)
gas_usage = api_client.get_service_usage(customer_id, account_id, 'gas', service_id)
```

## Configuration

### Environment Variables

The library supports environment variable configuration for both credentials and advanced settings.

#### Required Credentials

Create a `.env` file in your project root:

```bash
# Mercury Energy Account Credentials
MERCURY_EMAIL=your-email@example.com
MERCURY_PASSWORD=your-password
```

#### Optional Advanced Configuration

You can also override default OAuth and API settings:

```bash
# OAuth Configuration (optional - uses defaults if not specified)
MERCURY_CLIENT_ID=4c8c2c47-24cd-485d-aad9-12f3d95b3ceb
MERCURY_REDIRECT_URI=https://myaccount.mercury.co.nz
MERCURY_BASE_URL=https://login.mercury.co.nz/fc07dca7-cd6a-4578-952b-de7a7afaebdc
MERCURY_TIMEOUT=20

# API Configuration (optional - uses defaults if not specified)
MERCURY_API_BASE_URL=https://apis.mercury.co.nz/selfservice/v1
MERCURY_API_SUBSCRIPTION_KEY=f62040b20cf9401fb081880cb71c7dec
```

#### Environment Variable Reference

| Variable                       | Description                          | Required   | Default          |
| ------------------------------ | ------------------------------------ | ---------- | ---------------- |
| `MERCURY_EMAIL`                | Your Mercury Energy account email    | ✅ **Yes** | -                |
| `MERCURY_PASSWORD`             | Your Mercury Energy account password | ✅ **Yes** | -                |
| `MERCURY_CLIENT_ID`            | OAuth client ID                      | No         | Built-in default |
| `MERCURY_REDIRECT_URI`         | OAuth redirect URI                   | No         | Built-in default |
| `MERCURY_BASE_URL`             | OAuth base URL                       | No         | Built-in default |
| `MERCURY_TIMEOUT`              | Request timeout (seconds)            | No         | 20               |
| `MERCURY_API_BASE_URL`         | API base URL                         | No         | Built-in default |
| `MERCURY_API_SUBSCRIPTION_KEY` | API subscription key                 | No         | Built-in default |

#### Security Best Practices

- ✅ **Never commit `.env` files** to version control
- ✅ Use the provided `env.template` as a reference
- ✅ Each developer should have their own `.env` file
- ✅ Use environment variables in production deployments
- ✅ Regularly rotate your Mercury Energy password

#### Testing Environment Setup

You can verify your environment setup:

```bash
# Test credential loading
python3 -c "from mercury_examples import MERCURY_EMAIL; print('Email loaded:', MERCURY_EMAIL)"

# Run examples with your credentials
python3 mercury_examples.py
```

### Programmatic Configuration

```python
from pymercury import MercuryConfig, MercuryClient

config = MercuryConfig(
    client_id="your-client-id",
    api_subscription_key="your-api-key",
    timeout=30
)

client = MercuryClient("your-email@example.com", "your-password", config=config)
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
    client = MercuryClient("your-email@example.com", "your-password")
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

The library provides access to all Mercury.co.nz selfservice APIs, organized by functionality:

### Account Management

- `get_customer_info()` - Customer information and profile details
- `get_accounts()` - Account details and account listing
- `get_services()` - Service information across all accounts

### Billing & Financial

- `get_bill_summary()` - Current billing information and payment status

### Electricity Services

- `get_electricity_usage_content()` - Electricity usage content and disclaimers
- `get_electricity_usage()` - Daily electricity usage data with temperature
- `get_electricity_usage_hourly()` - Hourly electricity usage data
- `get_electricity_usage_monthly()` - Monthly electricity usage data
- `get_electricity_meter_info()` - Electricity meter details and status
- `get_electricity_meter_reads()` - Electricity meter reading history
- `get_electricity_plans()` - Available electricity plans and pricing

### Gas Services

- `get_gas_usage_content()` - Gas usage content and disclaimers
- `get_gas_usage()` - Daily gas usage data (no temperature data)
- `get_gas_usage_hourly()` - Hourly gas usage data
- `get_gas_usage_monthly()` - Monthly gas usage data

### Broadband Services

- `get_broadband_usage()` - Fibre broadband service info and daily usage data
- `get_fibre_usage()` - Fibre broadband service info and usage (alias for broadband)

### Generic/Cross-Service Methods

- `get_usage_content(service_type)` - Generic usage content for any service type
- `get_service_usage(service_type, ...)` - Generic usage data for any service type

## Requirements

- Python 3.7+
- `requests>=2.25.0`
- `python-dotenv>=1.0.0` (for environment variable support)

## Development

For development, install with optional dependencies:

```bash
pip install pymercury[dev]
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python3 run_tests.py

# Run specific test modules
python3 -m pytest tests/

# Run with coverage
python3 -m pytest tests/ --cov=pymercury
```

### Example Scripts

The repository includes comprehensive examples:

```bash
# Set up credentials first
cp env.template .env
# Edit .env with your actual Mercury Energy credentials

# Run all examples (requires real Mercury account)
python3 mercury_examples.py
```

The examples demonstrate:

- ✅ Authentication and token management
- ✅ Complete account data retrieval
- ✅ Electricity usage analysis and billing
- ✅ Gas usage content and data
- ✅ Broadband/Fibre service information
- ✅ Error handling and configuration
- ✅ Multi-service integration patterns

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For support, please open an issue on the GitHub repository.
