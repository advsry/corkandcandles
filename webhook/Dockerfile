# Azure Functions Python with ODBC Driver 18 for SQL Server
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# Install Microsoft ODBC Driver 18 for SQL Server (required for pyodbc)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 apt-transport-https \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

COPY requirements.txt /home/site/wwwroot/
RUN pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt

COPY . /home/site/wwwroot/
