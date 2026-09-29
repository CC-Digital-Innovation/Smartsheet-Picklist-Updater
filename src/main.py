import uvicorn

if __name__ == "__main__":
    uvicorn.run("smartsheet_picklist_updater:app", host="0.0.0.0", port = 8000, root_path="/picklistupdater")