# Bookeo → Excel Sync (Cork and Candles)

This application fetches booking data from the [Bookeo API](https://www.bookeo.com/apiref/#tag/Bookings) and writes it to an Excel spreadsheet. It is designed to run on an **Azure Virtual Machine** and can be scheduled to run periodically.

## Features

- **Historical data**: Fetches all bookings starting **January 1, 2026**
- **Future data**: Fetches all bookings **90 days** into the future from today
- **Excel output**: Single `.xlsx` file with columns for booking #, times, customer, product, price, canceled status, etc.
- **Canceled bookings**: Included by default (configurable)
- **API limits**: Automatically uses 31-day chunks and pagination (Bookeo allows max 31 days per call, 100 items per page)

## Requirements

- Python 3.10+ (or 3.9+)
- Azure VM (Linux or Windows) or any machine with Python

## Installation on Azure VM

### 1. Create an Azure VM

- Create an Ubuntu 22.04 LTS or Windows Server VM in Azure.
- SSH or RDP into the VM.

### 2. Install Python (if not present)

**Linux (Ubuntu):**

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

**Windows:** Install Python from [python.org](https://www.python.org/downloads/) or use the Microsoft Store.

### 3. Deploy the application

Copy this project to the VM (e.g. `C:\bookeo-sync` on Windows or `/opt/bookeo-sync` on Linux), or clone:

```bash
git clone <your-repo-url> /opt/bookeo-sync
cd /opt/bookeo-sync
```

### 4. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# or: venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 5. Configure credentials

The repo includes a `config.json` with your Bookeo credentials. For production:

- **Option A**: Keep `config.json` (already in `.gitignore`). Ensure the file is only readable by the app user.
- **Option B**: Use environment variables and do not store secrets in files:

  - `BOOKEO_API_KEY`
  - `BOOKEO_SECRET_KEY`
  - Optional: `BOOKEO_HISTORICAL_START`, `BOOKEO_FUTURE_DAYS`, `BOOKEO_OUTPUT_FILE`

Example (Linux):

```bash
export BOOKEO_API_KEY="your-api-key"
export BOOKEO_SECRET_KEY="your-secret-key"
```

### 6. Run the sync

```bash
python sync_bookeo_to_excel.py
```

Output file: `bookeo_bookings.xlsx` (or path set in config).

Optional:

- `--config path/to/config.json` — custom config file
- `--output path/to/output.xlsx` — override output path
- `--dry-run` — fetch and log count only; do not write Excel

## Scheduling (run automatically)

### Linux (cron)

Run every day at 6:00 AM:

```bash
crontab -e
```

Add (adjust paths to your install):

```
0 6 * * * /opt/bookeo-sync/venv/bin/python /opt/bookeo-sync/sync_bookeo_to_excel.py >> /opt/bookeo-sync/sync.log 2>&1
```

### Windows (Task Scheduler)

1. Open **Task Scheduler**.
2. Create Basic Task → name e.g. "Bookeo Excel Sync".
3. Trigger: Daily at 6:00 AM (or your preferred time).
4. Action: Start a program
   - Program: `C:\bookeo-sync\venv\Scripts\python.exe`
   - Arguments: `C:\bookeo-sync\sync_bookeo_to_excel.py`
   - Start in: `C:\bookeo-sync`
5. Finish and test by right-click → Run.

## Configuration

| Key                | Description                                            | Default                             |
| ------------------ | ------------------------------------------------------ | ----------------------------------- |
| `api_key`          | Bookeo API key                                         | (required)                          |
| `secret_key`       | Bookeo secret key                                      | (required)                          |
| `webhook_url`      | Webhook URL (for reference; webhook setup is separate) | https://corkandcandles.com/webhooks |
| `auth_api_id`      | Auth API ID (for reference)                            | —                                   |
| `historical_start` | Start of booking range (ISO datetime)                  | 2026-01-01T00:00:00Z                |
| `future_days`      | Days from today to include                             | 90                                  |
| `output_file`      | Path to output Excel file                              | bookeo_bookings.xlsx                |
| `include_canceled` | Include canceled bookings                              | true                                |

## Excel columns

The spreadsheet includes: Booking #, Start/End Time, Title, Product, Customer ID/Name/Email/Phone, Canceled status, Creation/Last change times and agents, Total Gross/Net/Paid, Currency, External Ref, Source, No Show, Resources, Options.

## Webhook URL

Your webhook URL (`https://corkandcandles.com/webhooks`) is stored in config for reference. To receive real-time booking events from Bookeo, you must register the webhook in the Bookeo API (POST `/webhooks`) and implement an HTTP endpoint at that URL that accepts Bookeo’s payloads. This sync script only **polls** the Bookeo API on a schedule; it does not start a web server or handle webhooks.

## Security note

- Do **not** commit `config.json` with real API keys to version control (it is in `.gitignore`).
- On Azure VM, restrict file permissions and consider using Azure Key Vault or VM-managed identity for secrets in production.

## Troubleshooting

- **"Missing api_key or secret_key"**: Set them in `config.json` or in `BOOKEO_API_KEY` and `BOOKEO_SECRET_KEY` environment variables.
- **Bookeo API error 401**: Check that `api_key` and `secret_key` are correct.
- **Bookeo API error 429**: You are being rate-limited; add a delay between runs or reduce frequency.
- **Empty Excel**: Verify the date range (e.g. `historical_start` and current date + `future_days`) contains bookings in your Bookeo account.

## API reference

- [Bookeo API – Bookings](https://www.bookeo.com/apiref/#tag/Bookings)
- Base URL: `https://api.bookeo.com/v2`
- Authentication: `apiKey` and `secretKey` as query parameters (or headers `X-Bookeo-apiKey`, `X-Bookeo-secretKey`).
