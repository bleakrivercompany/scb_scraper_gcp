from selenium import webdriver
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

print(dd.head(10))

print(dd.dtypes)

#dd = pd.read_csv('G:\Shared drives\Information Technology\Data Science\DataWarehouse\Dimension_Tables\Dates\Date_Dim.csv')

dd['date'] = pd.to_datetime(dd['date']).dt.date

CDate = pd.to_datetime('today').date()
# If I want to pull the last 2 months, you put the start at -2 months and max as 13
QRun_DT = CDate + pd.DateOffset(-60)
QRun = QRun_DT.date()

print(CDate)
print(QRun)
print(QRun_DT)


cdf = dd.loc[dd['date'] == QRun]
print(cdf.head())

cdf_sales_year = max(cdf['year'])
cdf_sales_month = min(cdf['month'])

print(cdf_sales_year)
print(cdf_sales_month)