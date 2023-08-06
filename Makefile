FILE_NAME := PBI Service Usage Reporting
GIT_REPO_NAME := pbi_PowerBIService_Usage
USER := $(shell powershell $$env:username)
FILE_LOCATION := "C:\Users\${USER}\OneDrive - C.H. Robinson\Power BI Reports\${FILE_NAME}.pbix"
CODEBASE := "C:\Power BI Code\${GIT_REPO_NAME}\power_bi"
RAW_DATA_FOLDER := "C:\Power BI Code\${GIT_REPO_NAME} Raw Data"
PID := $(shell powershell "Get-Process PBIDesktop | Where-Object {$$_.mainWindowTitle -eq \"${FILE_NAME} - Power BI Desktop\"} | select -expand Id")

# Extract the underlying codebase from your Power BI File
extract:
	pbi-tools extract ${FILE_LOCATION} -extractFolder ${CODEBASE}

# Auto-extract the codebase live every time you save your open Power BI file
# Start this command after opening your Power BI file and leave it running in the terminal
extract-watch:
	pbi-tools extract ${FILE_LOCATION} -extractFolder ${CODEBASE} -pid ${PID} -watch

# Create your Power BI File from the extracted codebase on your computer
compile:
	pbi-tools compile ${CODEBASE} -format PBIT -outPath ${FILE_LOCATION} -overwrite

# Open your Power BI File directly from the command line
launch-pbi:
	pbi-tools launch-pbi ${FILE_LOCATION}

# Export the raw data from your data model to CSV files
# Files are written to C:\Power BI Code\"Your Git Repo Name" Raw Data\ 
raw-data:
	pbi-tools export-data -pbixPath ${FILE_LOCATION} -outPath ${RAW_DATA_FOLDER}

# Run a SQL linter to standardize SQL Code Formatting
clean-sql:
	py ./sql_lint.py

# Run the codebase extraction and SQL linting processes together
extract-clean: extract clean-sql

# Run the codebase extraction, SQL linting, and Power BI file creation processes together
extract-clean-compile: extract clean-sql compile

# Run the codebase extraction, SQL linting, and Power BI file creation processes together, then open the file
all: extract clean-sql compile launch-pbi