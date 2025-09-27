# -*- coding: utf-8 -*-
"""
Created on Sat Jul 18 13:44:39 2020

@author: peter

This is the SCB Incremental Load and ETL

New function, get_buckets_csv takes two variables, defined by you at call
bucket_name = "your-gcs-bucket-name"
blob_name = "path/to/your/file.csv"

New function, save_buckets takes three, specifying the df first
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
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

# Define project
project_id = f"button-datawarehouse"
# Define storage bucket for push
bucket_name = "cs-royalties-test"  # Replace with your bucket name
# Define secrets to fetch
scb_username = get_gcp_secret(project_id, "scb_username", "latest")
scb_keys = get_gcp_secret(project_id, "scb_secretkeys", "latest")
secret_id_for_sa_key = "storage_sa_key" # The secret you just created
# get those secrets
sa_key_json_string = get_gcp_secret(project_id, secret_id_for_sa_key)
credentials_info = json.loads(sa_key_json_string)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
storage_client = storage.Client(credentials=credentials, project=project_id)

# Upload Full Product Query
# destination_blob_name = "dimension_tables/Product_Dim.csv"  # Desired filename in GCS
# bucket = storage_client.bucket(bucket_name)
# blob = bucket.blob(destination_blob_name)
# Upload the DataFrame as a CSV string
# blob.upload_from_string(Products_Run.to_csv(index=False), content_type="text/csv")

scb_start = datetime.now()

print("SCB Scrape Begin: ", scb_start)

# Date Dim load

dd_blob_name = "dimension_tables/Date_Dim.csv"

dd = get_bucket_csv(bucket_name, dd_blob_name)

print(dd.head())

#dd = pd.read_csv('G:\Shared drives\Information Technology\Data Science\DataWarehouse\Dimension_Tables\Dates\Date_Dim.csv')

dd['date'] = pd.to_datetime(dd['date']).dt.date

CDate = pd.to_datetime('today').date()
# If I want to pull the last 2 months, you put the start at -2 months and max as 13
QRun_DT = CDate + pd.DateOffset(-60)
QRun = QRun_DT.date()

#print(CDate)

cdf = dd.loc[dd['date'] == QRun]

cdf_sales_year = max(cdf['year'])
cdf_sales_month = min(cdf['month'])

# sales_run = pd.merge(dd, cdf[['SCB_Sales_Qtr']], on=['SCB_Sales_Qtr'])

# SCB_S_Qtr = max(sales_run['SCB_Sales_Qtr'])

# sales_year_auto = max(sales_run['year'])

years = np.arange(cdf_sales_year, cdf_sales_year + 1, 1)
months = np.arange(cdf_sales_month, 13, 1)
mm = calendar.month_name

# Initialize storage
# 1. Empty containers for table columns
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

#open Chrome
# FIX: Use a temporary, unique directory for the profile
# This directory will be created fresh every time the script runs (in /tmp/ which is cleared on reboot)
# The systemd service running as 'peter_gs' will have permission to write here.
# Change the old line: CHROME_PROFILE_PATH = '/home/peter_gs/.config/google-chrome/'
# to a new temporary one:
CHROME_TEMP_DATA_DIR = '/tmp/selenium-scb-profile'
# You main need to specify where the binary is
## --- Define the ABSOLUTE PATH to the Chrome binary ---
CHROME_BINARY_PATH = "/opt/google/chrome/chrome" 
# Open the Chrome Webdriver by specifying the path
# 1. Define the ABSOLUTE path to the ChromeDriver executable
CHROME_DRIVER_PATH = "/home/peter_gs/.cache/selenium/chromedriver/linux64/139.0.7258.154/chromedriver"
# NOTE: Replace '139.0.7258.154' with your actual version!

# 2. Instantiate the Service object
service = Service(executable_path=CHROME_DRIVER_PATH)

chrome_options = webdriver.ChromeOptions()

# CRITICAL OPTIONS FOR STABILITY
chrome_options.binary_location = CHROME_BINARY_PATH
chrome_options.add_argument("--headless=new") 
chrome_options.add_argument(f"--user-data-dir={CHROME_TEMP_DATA_DIR}") 
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# SECONDARY STABILITY OPTIONS
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--remote-debugging-port=9222") 
chrome_options.add_argument("--disable-setuid-sandbox")
# 3. Modify the driver instantiation to use the Service object
# 1. Instantiate the Service (CRITICAL: Use the explicit path found in your cache)
CHROME_DRIVER_CACHE_PATH = "/home/peter_gs/.cache/selenium/chromedriver/linux64/139.0.7258.154/chromedriver"
service = Service(executable_path=CHROME_DRIVER_CACHE_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options) # <-- USE THIS LINE
# Go to the SCB Distributors login page
driver.get('https://scbdistributors.com/cgi-bin/links/user.cgi')

# Find and Fill the Username and Password Fields
search_username = driver.find_element(By.NAME, 'Username')
# elem = driver.find_element(By.ID, 'm-documentationwebdriver')

search_username.send_keys(scb_username)

search_password = driver.find_element(By.NAME, 'Password')

search_password.send_keys(scb_keys)

# Submit the login

search_submit = driver.find_element(By.NAME, 'submit')

search_submit.click()

for report_year in years:
    for report_month in months:
        page = driver.get('https://scbdistributors.com/cgi-bin/sales/report.cgi?sf=Title&s=&report=monthly&so=Title&sot=&pr=All&m='+mm[report_month]+'&y='+str(report_year)+'&SUBMIT.x=17&SUBMIT.y=15')
        #print(page)

        # Show the html to verify you went to the right place

        soup = BeautifulSoup(driver.page_source, 'html.parser')


        print(soup.prettify())

        #identify the storage tags
        books_tr = soup.find_all('tr', {'bgcolor': ['#FFFFFF','#EDEDED']}, align='LEFT')
        # sleep for random interval between 2 and 10 seconds
        sleep(randint(2,10))



        #initiate the for loop
        #this tells your scraper to iterate through
        #every tr container we stored in books_tr

        for container in books_tr:

            Report_Yeardf.append(report_year)
            Report_Monthdf.append(mm[report_month])

            # TITLES
            bktitle = container.findAll(name='td')[0]
            bktitle = bktitle.text
            Book_Title.append(bktitle)

            # ISBN
            isbnn = container.findAll(name='td')[1]
            isbnn = float(isbnn.text)
            ISBN.append(isbnn)

            # Quantity Shipped
            qtyship = container.findAll(name='td')[2]
            qtyship = qtyship.text
            Quantity_Shipped.append(qtyship)

            # PUBLISHER PAYMENT
            pubpay = container.findAll(name='td')[3]
            pubpay = pubpay.text
            Publisher_Payment.append(pubpay)

            # QUANTITY RETURNED
            qtyret = container.findAll(name='td')[4]
            qtyret = qtyret.text
            Quantity_Returned.append(qtyret)

            # PUBLISHER CREDITS
            pubcred = container.findAll(name='td')[5]
            pubcred = pubcred.text
            Publisher_Credits.append(pubcred)

            # BEGINNING INVENTORY
            beginv = container.findAll(name='td')[6]
            beginv = beginv.text
            Beginning_Inventory.append(beginv)

            # QUANTITY RECEIVED
            qtyrec = container.findAll(name='td')[7]
            qtyrec = qtyrec.text
            Quantity_Received.append(qtyrec)

            # QUANTITY ADJUSTED
            qtyadj = container.findAll(name='td')[8]
            qtyadj = qtyadj.text
            Quantity_Adjusted.append(qtyadj)

            # ENDING INVENTORY
            endinv = container.findAll(name='td')[9]
            endinv = endinv.text
            Ending_Inventory.append(endinv)

print(Book_Title)
print(ISBN)
print(Quantity_Shipped)
print(Publisher_Payment)
print(Quantity_Returned)
print(Publisher_Credits)
print(Beginning_Inventory)
print(Quantity_Received)
print(Quantity_Adjusted)
print(Ending_Inventory)

Books = pd.DataFrame({
    'Month' : Report_Monthdf,
    'Month2' : Report_Monthdf,
    'Year' : Report_Yeardf,
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

print(Books)
print(Books.dtypes)

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

print(Books)
print(Books.dtypes)
print(Books.ISBN)

# Get MonthYears

Books['Month2'] = pd.to_datetime(Books['Month2'], format='%B').dt.month
print(Books['Month2'])

#pd.to_datetime(df.MONTH, format='%b').dt.month

Books = Books.sort_values(by=['Year', 'Month2'], ascending=[False, False])

Books = Books.drop(columns=['Month2'])

Books['MonthYear'] = Books['Month'] + Books['Year'].astype(str)

# def save_bucket(df, bucket_name: str, blob_name: str):

save_bucket(Books, bucket_name, 'stage/scb_stage/SCB_Increment_Stage.csv')

scb_end = datetime.now()

print("SCB Scrape Completed: ", scb_end)
scb_elapsed = scb_end - scb_start
print("Time Elapsed: ", scb_elapsed)
 #Exit out of the Chrome driver
driver.quit()