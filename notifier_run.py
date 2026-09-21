import json
import os
import re
import requests
import argparse
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Variables initialized to standard values
scriptLogFile = "/var/log/notifier_run.log"
maxLogSize = 10485760
maxLogFiles = 20
configPath = "notifier_settings.json"
targetId = ""
runAll = False

# Logger setup
logger = logging.getLogger("NotifierLogger")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(scriptLogFile, maxBytes=maxLogSize, backupCount=maxLogFiles)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def parseArguments():
    global configPath, targetId, runAll
    try:
        parser = argparse.ArgumentParser(description="Log Notifier Script")
        parser.add_argument("-c", "--config", help="Path to config file", default="notifier_settings.json")
        parser.add_argument("-i", "--id", help="Execute specific logId", default="")
        parser.add_argument("-a", "--all", help="Execute all logs", action="store_true")
        
        args = parser.parse_args()
        configPath = args.config
        targetId = args.id
        runAll = args.all
    except Exception as e:
        logger.error(f"Error parsing arguments: {e}")

def loadConfig(path):
    try:
        if not os.path.exists(path):
            logger.error(f"Configuration file not found: {path}")
            return None
        with open(path, 'r') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return None

def sendWebhook(url, method, headers, payload):
    try:
        method = method.upper()
        if method == "POST":
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=payload, timeout=10)
        elif method == "GET":
            response = requests.get(url, headers=headers, params=payload, timeout=10)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return

        response.raise_for_status()
        logger.info(f"Webhook sent successfully to {url}")
    except Exception as e:
        logger.error(f"Webhook execution failed: {e}")

def processLog(logConfig, globalConfig):
    # Variables initialized to standard values
    logFilePath = logConfig.get("filePath", "")
    logId = logConfig.get("logId", "unknown")
    startPatternStr = logConfig.get("startPattern", "")
    useDateFilter = logConfig.get("useDateFilter", False)
    dateFormat = logConfig.get("dateFormat", "%Y-%m-%d")
    checkRotatedLogs = logConfig.get("checkRotatedLogs", True)
    rotationSuffix = logConfig.get("rotationSuffix", ".1")
    patterns = logConfig.get("patterns", [])
    
    webhookUrl = logConfig.get("webhookUrl", "")
    if not webhookUrl:
        webhookUrl = globalConfig.get("webhookUrl", "")
        
    method = logConfig.get("method", "POST")
    title = logConfig.get("title", "")
    if not title and logFilePath:
        title = os.path.basename(logFilePath)

    headers = globalConfig.get("headers", {}).copy()
    headers.update(logConfig.get("headers", {}))

    todayDateStr = datetime.now().strftime(dateFormat)
    matchedResults = []
    highestPriority = 0
    blockFound = False

    filePathsToSearch = [logFilePath]
    if checkRotatedLogs:
        filePathsToSearch.append(f"{logFilePath}{rotationSuffix}")

    try:
        for currentFile in filePathsToSearch:
            if not os.path.exists(currentFile):
                continue
                
            with open(currentFile, 'r') as file:
                lines = file.readlines()
                
            # Reverse loop (bottom-up parsing)
            for line in reversed(lines):
                if useDateFilter and todayDateStr not in line:
                    continue
                    
                if startPatternStr and startPatternStr in line:
                    blockFound = True
                    break

                for pat in patterns:
                    regexStr = pat.get("regex", "")
                    prio = pat.get("priority", 0)
                    
                    match = re.search(regexStr, line)
                    if match:
                        matchedText = match.group(0)
                        if len(match.groups()) > 0:
                            matchedText = " ".join(match.groups())
                        
                        matchedResults.append(matchedText)
                        if prio > highestPriority:
                            highestPriority = prio

            if blockFound:
                break

        if matchedResults:
            # Re-reverse results to chronological order
            matchedResults.reverse()
            summaryMessage = "\n".join(matchedResults)
            
            payload = {
                "title": title,
                "message": summaryMessage,
                "priority": highestPriority
            }
            sendWebhook(webhookUrl, method, headers, payload)
        else:
            logger.info(f"No patterns matched for logId: {logId}")

    except Exception as e:
        logger.error(f"Error processing log {logId}: {e}")

def main():
    try:
        parseArguments()
        
        if not targetId and not runAll:
            logger.info("No execution target specified. Use --all or --id.")
            return

        configData = loadConfig(configPath)
        if not configData:
            return

        globalConfig = configData.get("global", {})
        logsConfig = configData.get("logs", [])

        for logItem in logsConfig:
            currentId = logItem.get("logId", "")
            if runAll or currentId == targetId:
                logger.info(f"Processing logId: {currentId}")
                processLog(logItem, globalConfig)

    except Exception as e:
        logger.error(f"Critical failure in main script: {e}")

if __name__ == "__main__":
    main()