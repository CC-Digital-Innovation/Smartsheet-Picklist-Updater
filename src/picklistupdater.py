from fastapi import Depends, FastAPI, HTTPException, status, Header, Body
from pathlib import PurePath
import dotenv
import os
import smartsheet
import tempfile
import csv
import hmac
import json

#load secrets from environemnt variables defined in deployement
dotenv.load_dotenv(PurePath(__file__).with_name('.env'))

#assign environment variables to globals
SMARTSHEET_API_TOKEN = os.getenv('SMARTSHEET_API_TOKEN')
SMARTSHEET_WEBHOOK_SHAREDSECRET = os.getenv('SHARED_SECRET')
SMARTSHEET_TIME_TRACKING_FOLDER_IDs = os.getenv('SMARTSHEET_TIME_TRACKING_FOLDER_ID')
SMARTSHEET_TIME_TRACKING_FOLDER_IDs_list = SMARTSHEET_TIME_TRACKING_FOLDER_IDs.split(',')
MASTER_CUST_LIST_SHEET_ID = os.getenv("MASTER_CUST_LIST_SHEET_ID")
MASTER_CUST_LIST_SHEET_NAME = os.getenv("MASTER_SHEET_NAME")

encrypt = hmac.new(SMARTSHEET_WEBHOOK_SHAREDSECRET.encode(), digestmod='sha256')

#init app - rename with desired app name
app = FastAPI()

#init key for auth

#auth key
def authorize(body, checkvalue):
    encrypt.update(body.encode())
    if not encrypt.hexdigest()==checkvalue:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid token')


def picklist_distribution(customer_options: list):
    # Initialize the connection to the Smartsheet client.
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_API_TOKEN)
    sheetslist = []

    # Get all sheets from the time tracking folder.
    for folder in SMARTSHEET_TIME_TRACKING_FOLDER_IDs_list:
        time_tracking_folder = smartsheet_client.Folders.get_folder(folder)
        all_time_tracking_sheets = time_tracking_folder.sheets.to_list()
        for eachlist in all_time_tracking_sheets:
            sheetslist.append(eachlist)

    # Make the new customer options column to update all the sheets with.
    new_customer_options_column = smartsheet.models.Column(
        {
            'title': 'Customer Name',
            'type': 'PICKLIST',
            'options': customer_options,
            'index': 2
        }
    )

    # Update the customer name column in each sheet in the folder.
    for time_tracking_sheet in sheetslist:
        # Get all the columns of this sheet.
        list_columns_response = smartsheet_client.Sheets.get_columns(
            time_tracking_sheet.id_
        )

        # Get the ID of the customer name column.
        customer_name_column_id = list_columns_response.data[2].id_
    
        # Update the customer name column in the sheet.
        update_column_response = smartsheet_client.Sheets.update_column(
            time_tracking_sheet.id_,
            customer_name_column_id,
            new_customer_options_column
        )

        # Output if the update was successful or not.
        if update_column_response.message == 'SUCCESS':
            print(f'{time_tracking_sheet.name}\'s time tracking sheet was successfully updated!')
        else:
            print(f'Error updating {time_tracking_sheet.name}\'s time tracking sheet | '
                  f'Result Code: {update_column_response.result_code}')\

def get_customer_list(sheetid):
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_API_TOKEN)
    custlist=[]
    with tempfile.TemporaryDirectory() as csvdir:
        smartsheet_client.Sheets.get_sheet_as_csv(sheetid, csvdir)
        with open(os.path.join(csvdir, f'{MASTER_CUST_LIST_SHEET_NAME}.csv'), 'r') as file:
            csvread = csv.reader(file, delimiter='\n')
            for row in csvread:
                cols = row[0].split(',')
                custlist.append(cols[0])
    custlist.pop(0)
    return custlist

#sample post
@app.post('/picklistupdater')
def sample_post(body: dict = Body(), Smartsheet_Hmac_SHA256: str | None = Header(default=None)):
    print(Smartsheet_Hmac_SHA256)
    print(body)
    if "challenge" in body.keys():
        return {"smartsheetHookResponse" : body['challenge']}
    else:
        Depends(authorize(json.dumps(body, separators=(',', ':')), Smartsheet_Hmac_SHA256))
        custs = get_customer_list(MASTER_CUST_LIST_SHEET_ID)
        picklist_distribution(custs)
    



