import json
import os
import logging
import readline
from logging.handlers import RotatingFileHandler

# Autocomplete setup for paths
readline.parse_and_bind("tab: complete")

# Variables initialized to standard values
settingsFilePath = "notifier_settings.json"
logFilePath = "/var/log/notifier_setup.log"
maxLogSize = 10485760
maxLogFiles = 20

# Logger setup
logger = logging.getLogger("SetupLogger")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(logFilePath, maxBytes=maxLogSize, backupCount=maxLogFiles)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def loadConfig():
    try:
        if os.path.exists(settingsFilePath):
            with open(settingsFilePath, 'r') as file:
                return json.load(file)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        
    return {
        "global": {
            "webhookUrl": "http://YOUR-SERVER/message?token=DEFAULT",
            "headers": {"Content-Type": "application/json"}
        },
        "logs": []
    }

def saveConfig(configData):
    try:
        with open(settingsFilePath, 'w') as file:
            json.dump(configData, file, indent=4)
        logger.info("Configuration saved successfully.")
        print("Configuration saved successfully.")
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        print(f"Error saving configuration: {e}")

def prompt(text, defaultVal=""):
    if defaultVal:
        userInput = input(f"{text} [{defaultVal}]: ").strip()
    else:
        userInput = input(f"{text}: ").strip()
    return userInput if userInput else defaultVal

def displayConfig(configData):
    print("\n--- Current Configuration ---")
    print(f"Global Webhook URL: {configData.get('global', {}).get('webhookUrl', '')}")
    print("\nConfigured Logs:")
    logs = configData.get("logs", [])
    if not logs:
        print("  No logs configured.")
    for idx, logItem in enumerate(logs):
        print(f"  [{idx}] ID: {logItem.get('logId')} | File: {logItem.get('filePath')}")
    print("-----------------------------\n")

def editConfig(configData):
    try:
        print("1 - Edit Global Settings")
        print("2 - Edit Log Config")
        editChoice = prompt("Select option", "1")
        
        if editChoice == "1":
            globalCfg = configData.get("global", {})
            globalCfg["webhookUrl"] = prompt("Webhook URL", globalCfg.get("webhookUrl", ""))
            configData["global"] = globalCfg
            print("Global settings updated.")
            
        elif editChoice == "2":
            logs = configData.get("logs", [])
            if not logs:
                print("No logs available to edit.")
                return
            logIndexStr = prompt("Enter log index to edit", "0")
            
            logIndex = int(logIndexStr)
            if 0 <= logIndex < len(logs):
                logItem = logs[logIndex]
                logItem["logId"] = prompt("Log ID", logItem.get("logId", ""))
                logItem["filePath"] = prompt("Log File Path", logItem.get("filePath", ""))
                logItem["webhookUrl"] = prompt("Webhook URL", logItem.get("webhookUrl", ""))
                logItem["method"] = prompt("HTTP Method", logItem.get("method", "POST"))
                logItem["title"] = prompt("Notification Title", logItem.get("title", ""))
                
                filterStr = prompt("Use Date Filter? (true/false)", str(logItem.get("useDateFilter", False)).lower())
                logItem["useDateFilter"] = filterStr.lower() == "true"
                logItem["dateFormat"] = prompt("Date Format", logItem.get("dateFormat", "%Y-%m-%d"))
                
                logItem["startPattern"] = prompt("Start Pattern", logItem.get("startPattern", ""))
                
                rotStr = prompt("Check rotated logs? (true/false)", str(logItem.get("checkRotatedLogs", True)).lower())
                logItem["checkRotatedLogs"] = rotStr.lower() == "true"
                logItem["rotationSuffix"] = prompt("Rotation Suffix", logItem.get("rotationSuffix", ".1"))
                
                print(f"Log [{logIndex}] updated.")
            else:
                print("Invalid index.")
    except Exception as e:
        logger.error(f"Error editing config: {e}")
        print(f"Error: {e}")

def addConfig(configData):
    try:
        newLog = {}
        newLog["logId"] = prompt("Log ID", "newAppLog")
        newLog["filePath"] = prompt("Log File Path", "/var/log/app.log")
        newLog["webhookUrl"] = prompt("Webhook URL (leave empty to use global)", "")
        newLog["method"] = prompt("HTTP Method", "POST")
        newLog["title"] = prompt("Notification Title", newLog["logId"])
        
        filterStr = prompt("Use Date Filter? (true/false)", "false")
        newLog["useDateFilter"] = filterStr.lower() == "true"
        newLog["dateFormat"] = prompt("Date Format", "%Y-%m-%d")
        
        newLog["startPattern"] = prompt("Start Pattern", "")
        
        rotStr = prompt("Check rotated logs? (true/false)", "true")
        newLog["checkRotatedLogs"] = rotStr.lower() == "true"
        newLog["rotationSuffix"] = prompt("Rotation Suffix", ".1")
        
        patterns = []
        while True:
            addPattern = prompt("Add a regex pattern? (yes/no)", "no")
            if addPattern.lower() != "yes":
                break
            
            patternObj = {}
            patternObj["regex"] = prompt("Regex Pattern", "error")
            prioStr = prompt("Priority", "5")
            try:
                patternObj["priority"] = int(prioStr)
            except ValueError:
                patternObj["priority"] = 5
                
            patterns.append(patternObj)
            
        newLog["patterns"] = patterns
        configData["logs"].append(newLog)
        print(f"Log ID '{newLog['logId']}' added.")
    except Exception as e:
        logger.error(f"Error adding config: {e}")
        print(f"Error: {e}")

def removeConfig(configData):
    try:
        logs = configData.get("logs", [])
        if not logs:
            print("No logs available to remove.")
            return
            
        logIndexStr = prompt("Enter log index to remove", "")
        logIndex = int(logIndexStr)
        if 0 <= logIndex < len(logs):
            removedLog = logs.pop(logIndex)
            print(f"Removed log ID: {removedLog.get('logId')}")
        else:
            print("Invalid index.")
    except Exception as e:
        logger.error(f"Error removing config: {e}")
        print("Invalid input or error.")

def main():
    try:
        configData = loadConfig()
        while True:
            displayConfig(configData)
            print("1 - Edit")
            print("2 - Add")
            print("3 - Remove")
            print("4 - Save & Exit")
            print("5 - Exit without saving")
            
            actionChoice = prompt("Select action", "4")
            
            if actionChoice == "1":
                editConfig(configData)
            elif actionChoice == "2":
                addConfig(configData)
            elif actionChoice == "3":
                removeConfig(configData)
            elif actionChoice == "4":
                saveConfig(configData)
                break
            elif actionChoice == "5":
                print("Exiting without saving.")
                break
            else:
                print("Invalid choice.")
    except Exception as e:
        logger.error(f"Critical process failed: {e}")
        print(f"Critical error: {e}")

if __name__ == "__main__":
    main()