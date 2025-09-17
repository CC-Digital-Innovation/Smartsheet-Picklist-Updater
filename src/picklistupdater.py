from fastapi import Depends, FastAPI, HTTPException, status, Header, Body, BackgroundTasks
from pathlib import PurePath
import dotenv
import os
import smartsheet
import tempfile
import csv
import hmac
import json
from loguru import logger

#load secrets from environemnt variables defined in deployement
dotenv.load_dotenv(PurePath(__file__).with_name('.env'))

#assign environment variables to globals
SMARTSHEET_API_TOKEN = os.getenv('SMARTSHEET_API_TOKEN')
SMARTSHEET_WEBHOOK_SHAREDSECRET = os.getenv('SHARED_SECRET')
SMARTSHEET_CONTRACT_WEBHOOK_SHAREDSECRET = os.getenv('CONTRACT_SHARED_SECRET')
SMARTSHEET_TIME_TRACKING_FOLDER_IDs = os.getenv('SMARTSHEET_TIME_TRACKING_FOLDER_ID')
SMARTSHEET_TIME_TRACKING_FOLDER_IDs_list = SMARTSHEET_TIME_TRACKING_FOLDER_IDs.split(',')
MASTER_CUST_LIST_SHEET_ID = os.getenv("MASTER_CUST_LIST_SHEET_ID")
MASTER_CUST_LIST_SHEET_NAME = os.getenv("MASTER_SHEET_NAME")
MASTER_CONTRACT_LIST_SHEET_ID = os.getenv("MASTER_CONTRACT_LIST_SHEET_ID")
CONTRACT_FOLDERS_IDS=os.getenv('CONTRACT_TRACKING_FOLDER_ID')
CONTRACT_TRACKING_FOLDER_IDs_list = CONTRACT_FOLDERS_IDS.split(',')



#init app - rename with desired app name
app = FastAPI()

#init key for auth

#auth key
def authorize(body, checkvalue, webhooksecret):
    encrypt = hmac.new(webhooksecret.encode(), body.encode(), digestmod='sha256')
    decrypt = encrypt.hexdigest()
    logger.info(f"Recieved in Header: {checkvalue}")
    logger.info(f"hashed:             {decrypt}")
    if not decrypt==checkvalue:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid token')


def picklist_distribution(customer_options: list, col_num: int, col_title, folders):
    # Initialize the connection to the Smartsheet client.
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_API_TOKEN)
    sheetslist = []

    # Get all sheets from the time tracking folder.
    for folder in folders:
        time_tracking_folder = smartsheet_client.Folders.get_folder(folder)
        all_time_tracking_sheets = time_tracking_folder.sheets.to_list()
        for eachlist in all_time_tracking_sheets:
            sheetslist.append(eachlist)

    # Make the new customer options column to update all the sheets with.
    new_customer_options_column = smartsheet.models.Column(
        {
            'title': col_title,
            'type': 'PICKLIST',
            'options': customer_options,
            'index': col_num
        }
    )

    # Update the customer name column in each sheet in the folder.
    for time_tracking_sheet in sheetslist:
        # Get all the columns of this sheet.
        list_columns_response = smartsheet_client.Sheets.get_columns(
            time_tracking_sheet.id_
        )

        # Get the ID of the customer name column.
        customer_name_column_id = list_columns_response.data[col_num].id_
    
        # Update the customer name column in the sheet.
        update_column_response = smartsheet_client.Sheets.update_column(
            time_tracking_sheet.id_,
            customer_name_column_id,
            new_customer_options_column
        )

        # Output if the update was successful or not.
        if update_column_response.message == 'SUCCESS':
            logger.info(f'{time_tracking_sheet.name}\'s time tracking sheet was successfully updated!')
        else:
            logger.info(f'Error updating {time_tracking_sheet.name}\'s time tracking sheet | '
                  f'Result Code: {update_column_response.result_code}')
    logger.info("Done updating Sheets. Exiting distribution function")

def get_customer_list(sheetid):
    smartsheet_client = smartsheet.Smartsheet(access_token=SMARTSHEET_API_TOKEN)
    custlist=[]
    logger.info("Grabing temp csv to extract list from column 1 of source sheet")
    with tempfile.TemporaryDirectory() as csvdir:
        smartsheet_client.Sheets.get_sheet_as_csv(sheetid, csvdir)
        with open(os.path.join(csvdir, 'download.csv'), 'r') as file:
            csvread = csv.reader(file, delimiter='\n')
            for row in csvread:
                cols = row[0].split(',')
                custlist.append(cols[0])
    custlist.pop(0)
    logger.info("list complete. returning items to caller function")
    return custlist

def funcCaller(sheetid, col_num, col_title, folders):
    logger.debug(f"creating list of items from sheet: {sheetid}")
    custs = get_customer_list(sheetid)
    logger.debug(f"distributing list")
    picklist_distribution(custs, col_num, col_title, folders)
    logger.info("Distribution complete, exiting stack")



#Customer Picklist
@app.post('/picklistupdater', status_code=200)
async def sample_post(tasks: BackgroundTasks, body: dict = Body(), Smartsheet_Hmac_SHA256: str | None = Header(default=None)):
    logger.info("Payload recieved from Smartsheets for Customer List update")
    if "challenge" in body.keys():
        logger.info("Challenge Ack")
        return {"smartsheetHookResponse" : body['challenge']}
    else:
        Depends(authorize(json.dumps(body, separators=(',', ':')), Smartsheet_Hmac_SHA256, SMARTSHEET_WEBHOOK_SHAREDSECRET))
        logger.info("Authorized")
        folders = SMARTSHEET_TIME_TRACKING_FOLDER_IDs_list
        logger.debug(f"Folder IDs: {folders}")
        logger.debug(f"Starting background task with Customers from {MASTER_CUST_LIST_SHEET_ID} for column 3: Customer Name")
        tasks.add_task(funcCaller, MASTER_CUST_LIST_SHEET_ID, 2, 'Customer Name', folders)
        logger.info("Responding to webhook")
        return {"Callback Message" : "Callback recieved, proccessing update"}
    
#contract picklist
@app.post('/contractpicklistupdater', status_code=200)
async def sample_post(tasks: BackgroundTasks, body: dict = Body(), Smartsheet_Hmac_SHA256: str | None = Header(default=None)):
    logger.info("Payload recieved from Smartsheets for Opportunity List update")
    if "challenge" in body.keys():
        logger.info("Challenge Ack")
        return {"smartsheetHookResponse" : body['challenge']}
    else:
        Depends(authorize(json.dumps(body, separators=(',', ':')), Smartsheet_Hmac_SHA256, SMARTSHEET_CONTRACT_WEBHOOK_SHAREDSECRET))
        logger.info("Authorized")
        folders = CONTRACT_TRACKING_FOLDER_IDs_list
        logger.info(f"Folder IDs: {folders}")
        logger.debug(f"Starting background task with Customers from {MASTER_CONTRACT_LIST_SHEET_ID} for column 3: Customer Name")
        tasks.add_task(funcCaller, MASTER_CONTRACT_LIST_SHEET_ID, 3, 'Opportunity Number', folders)
        logger.info("Responding to webhook")
        return {"Callback Message" : "Callback recieved, proccessing update"}
    



