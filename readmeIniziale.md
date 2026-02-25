# Contract Geek Mass Workflow Script

## Overview
This script processes files in a specified directory and its subdirectories, sending PDF files to the Contract Geek API. The subfolder name is used to identify the corresponding "Controparte," and the script skips over files and folders that do not meet the expected criteria.

The script also includes dynamic identification of signature tag positions within PDF files.

## Install Dependencies
   This project comes with a pre-configured Python virtual environment (`venv`) that already includes all required libraries.  
   However, if needed, the main external packages used are:
   - [requests](https://pypi.org/project/requests/): for making HTTP requests
   - [pypdf](https://pypi.org/project/pypdf/): for reading and manipulating PDF files

## Data Folder
The `data` folder must always contain the following three files, each with the expected structure:

---

### `config.json`
Contains the main configuration for the application.
```json
{
    "api_key": "your_api_key",
    "destination_path": "Absolute/Path/Where/File/Will/Be/Moved/After/Being/Processed",
    "organization_id": "your_organization_id",
    "workspace_id": "your_workspace_id",
    "endpoint": "application_endpoint",
    "folder_path": "Absolute/Path/To/Storage/Folder",
    "file_log_path": "Absolute/Path/To/Log/app.log"
}
```

---

### `signbox_map.json`
Defines the position of the signbox. Must contain **exactly three entries**, each with the following structure:
```json
{
    "SignatureField1": {
        "x": int,
        "y": int,
        "width": int,
        "height": int
    },
    "SignatureField2": {
        "x": int,
        "y": int,
        "width": int,
        "height": int
    },
    "SignatureField3": {
        "x": int,
        "y": int,
        "width": int,
        "height": int
    }
}
```

---

### `user_map.json`
Maps internal user identifiers to workspace IDs. The key `"Legale Rappresentante OrganizationName"` must always be present as-is.  
Replace `OrganizationName` with your actual organization name.  
`"Workspace 1"` to `"Workspace n"` are placeholders for actual workspace names.
```json
{
    "Legale Rappresentante OrganizationName": int,
    "Workspace 1": int,
    "Workspace 2": int,
    "...": "...",
    "Workspace n": int
}
```

## Notes
- Make sure that both the `folder_path` and the `destination_path` specified in the `config.json` file are valid, accessible directories. The former should contain the files to be processed, and the latter is where processed files will be moved.
- The script automatically **skips non-PDF files**
- The script logs a warning if it encounters folders without a corresponding `Controparte`.
- In case of irregularities during processing (e.g., missing mappings, invalid structure, too many users in a controparte), the workflow is left in **Bozza** status and will not proceed to completion.
- Logs are written both to the **console** and to the file defined in `file_log_path`.

If you encounter issues or have questions, please refer to the in-code comments for further clarification.
