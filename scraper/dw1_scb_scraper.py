# -*- coding: utf-8 -*-
"""
SCB Incremental Load and ETL

Retrieves data from SCB Distributors, processes date dimensions, and uploads
the incremental data to Google Cloud Storage (GCS).

Functions Used:
- get_gcp_secret: Fetches secrets (e.g., credentials, keys) from GCP Secret Manager.
- get_bucket_csv: Downloads a CSV file from GCS into a Pandas DataFrame.
- save_bucket: Uploads a Pandas DataFrame to a specified GCS location as a CSV.
"""
# ----------------------------------------------------------------------
# 1. IMPORTS
# ----------------------------------------------------------------------
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options # <--- MISSING IMPORT ADDED
from selenium.webdriver.common.by import By
import pandas as pd
from bs4 import BeautifulSoup
import numpy as np
from time import sleep
from random import randint
import calendar
from datetime import date
from datetime import datetime
from google.cloud import storage
from google.cloud import secretmanager
from google.api_core import exceptions
from gcp_getsecret2 import get_gcp_secret
from gcp_getbucket import get_bucket_csv
from gcp_postbucket import save_bucket
import json
from google.oauth2 import service_account


# ----------------------------------------------------------------------
# 2. CONFIGURATION & GCS SETUP
# ----------------------------------------------------------------------
project_id = "button-datawarehouse"
bucket_name = "cs-royalties-test"  # Target storage bucket
scb_start = datetime.now()

print("SCB Scrape Begin: ", scb_start)

# --- Secret Manager and GCS Client Initialization ---
scb_username = get_gcp_secret(project_id, "scb_username", "latest")
scb_keys = get_gcp_secret(project_id, "scb_secretkeys", "latest")
secret_id_for_sa_key = "storage_sa_key"

sa_key_json_string = get_gcp_secret(project_id, secret_id_for_sa_key)
credentials_info = json.loads(sa_key_json_string)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
storage_client = storage.Client(credentials=credentials, project=project_id)

# ----------------------------------------------------------------------
# 3. DATE DIMENSION LOGIC
# ----------------------------------------------------------------------
dd_blob_name = "dimension_tables/Date_Dim.csv"
dd = get_bucket_csv(bucket_name, dd_blob_name)
print(dd.head())

dd['date'] = pd.to_datetime(dd['date']).dt.date
CDate = pd.to_datetime('today').date()
# Calculate start date for 60 days back
QRun_DT = CDate + pd.DateOffset(-60)
QRun = QRun_DT.date()

cdf = dd.loc[dd['date'] == QRun]

cdf_sales_year = max(cdf['year'])
cdf_sales_month = min(cdf['month'])

years = np.arange(cdf_sales_year, cdf_sales_year + 1, 1)
months = np.arange(cdf_sales_month, 13, 1)
mm = calendar.month_name

# ----------------------------------------------------------------------
# 4. SELENIUM / CHROME SETUP
# ----------------------------------------------------------------------
CHROME_TEMP_DATA_DIR = '/tmp/selenium-scb-profile'
CHROME_BINARY_PATH = "/opt/google/chrome/chrome"
CHROME_DRIVER_PATH = "/home/peter_gs/.cache/selenium/chromedriver/linux64/139.0.7258.154/chromedriver"

# 1. Instantiate the Service (ONCE)
service = Service(executable_path=CHROME_DRIVER_PATH, start_session_timeout=180) # <--- ADDED TIMEOUT

# 2. Configure Options
chrome_options = Options()
chrome_options.binary_location = CHROME_BINARY_PATH
chrome_options.add_argument("--headless=new")
chrome_options.add_argument(f"--user-data-dir={CHROME_TEMP_DATA_DIR}")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--single-process")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--silent")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-setuid-sandbox")

# 3. Data Containers
Book_Title = []
ISBN = []
Quantity_Shipped = []
Publisher_Payment = []
Quantity_Returned = []
Publisher_Credits = []
Beginning_Inventory = []
Quantity_Received = []
Quantity_Adjusted = []
Ending_Inventory = []
Report_Yeardf = []
Report_Monthdf = []


# ----------------------------------------------------------------------
# 5. EXECUTION BLOCK (TRAP ERRORS HERE)
# ----------------------------------------------------------------------
try:
    # 🛑 CRITICAL: Driver instantiation is here. 
    # The rest of the script must be indented inside the 'try' block.
    driver = webdriver.Chrome(service=service, options=chrome_options) 
    
    # --- LOGIN ---
    driver.get('https://scbdistributors.com/cgi-bin/links/user.cgi')

    search_username = driver.find_element(By.NAME, 'Username')
    search_username.send_keys(scb_username)

    search_password = driver.find_element(By.NAME, 'Password')
    search_password.send_keys(scb_keys)

    search_submit = driver.find_element(By.NAME, 'submit')
    search_submit.click()
    
    # --- SCRAPING LOOP ---
    for report_year in years:
        for report_month in months:
            # Navigate to report page
            driver.get('https://scbdistributors.com/cgi-bin/sales/report.cgi?sf=Title&s=&report=monthly&so=Title&sot=&pr=All&m='+mm[report_month]+'&y='+str(report_year)+'&SUBMIT.x=17&SUBMIT.y=15')
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            print(soup.prettify())

            books_tr = soup.find_all('tr', {'bgcolor': ['#FFFFFF','#EDEDED']}, align='LEFT')
            sleep(randint(2,10))

            # --- DATA EXTRACTION ---
            for container in books_tr:
                Report_Yeardf.append(report_year)
                Report_Monthdf.append(mm[report_month])

                # Extraction logic (kept as is, but should ideally have inner try/except for robust ETL)
                Book_Title.append(container.findAll(name='td')[0].text)
                ISBN.append(float(container.findAll(name='td')[1].text))
                Quantity_Shipped.append(container.findAll(name='td')[2].text)
                Publisher_Payment.append(container.findAll(name='td')[3].text)
                Quantity_Returned.append(container.findAll(name='td')[4].text)
                Publisher_Credits.append(container.findAll(name='td')[5].text)
                Beginning_Inventory.append(container.findAll(name='td')[6].text)
                Quantity_Received.append(container.findAll(name='td')[7].text)
                Quantity_Adjusted.append(container.findAll(name='td')[8].text)
                Ending_Inventory.append(container.findAll(name='td')[9].text)

    # Print collected data (optional, but good for logs)
    # print(Book_Title, ISBN, ...)

    # ----------------------------------------------------------------------
    # 6. DATAFRAME CREATION & CLEANUP
    # ----------------------------------------------------------------------
    Books = pd.DataFrame({
        'Month' : Report_Monthdf,
        'Month2' : Report_Monthdf,
        'Year' : Report_Yeardf,
        # ... (rest of your DataFrame definition) ...
        'Title' : Book_Title,
        'ISBN' : ISBN,
        'Quantity Shipped' : Quantity_Shipped,
        'Publisher Payment' : Publisher_Payment,
        'Quantity Returned' : Quantity_Returned,
        'Publisher Credits' : Publisher_Credits,
        'Beginning Inventory' : Beginning_Inventory,
        'Quantity Received' : Quantity_Received,
        'Quantity Adjusted' : Quantity_Adjusted,
        'Ending Inventory' : Ending_Inventory,
        })

    # Type Casting/Data Cleaning
    Books['Year'] = Books['Year'].astype(int)
    Books['ISBN'] = Books['ISBN'].astype(str)
    Books['Title'] = Books['Title'].str.replace(',', '').astype(object)
    Books['Quantity Shipped'] = Books['Quantity Shipped'].astype(int)
    Books['Publisher Payment'] = Books['Publisher Payment'].astype(float)
    Books['Quantity Returned'] = Books['Quantity Returned'].astype(int)
    Books['Publisher Credits'] = Books['Publisher Credits'].astype(float)
    Books['Beginning Inventory'] = Books['Beginning Inventory'].astype(int)
    Books['Quantity Received'] = Books['Quantity Received'].astype(int)
    Books['Quantity Adjusted'] = Books['Quantity Adjusted'].astype(int)
    Books['Ending Inventory'] = Books['Ending Inventory'].astype(int)

    # MonthYear creation
    Books['Month2'] = pd.to_datetime(Books['Month2'], format='%B').dt.month
    Books = Books.sort_values(by=['Year', 'Month2'], ascending=[False, False])
    Books = Books.drop(columns=['Month2'])
    Books['MonthYear'] = Books['Month'] + Books['Year'].astype(str)

    # ----------------------------------------------------------------------
    # 7. UPLOAD & COMPLETION
    # ----------------------------------------------------------------------
    save_bucket(Books, bucket_name, 'stage/scb_stage/SCB_Increment_Stage.csv')

    scb_end = datetime.now()
    print("SCB Scrape Completed: ", scb_end)
    scb_elapsed = scb_end - scb_start
    print("Time Elapsed: ", scb_elapsed)

except Exception as e:
    print(f"FATAL ERROR DURING SCRAPE EXECUTION: {e}")
    # Re-raise the exception so systemd marks the service as failed
    raise

finally:
    # CRITICAL: Ensures the browser session is closed even if an error occurs
    if 'driver' in locals():
        driver.quit()