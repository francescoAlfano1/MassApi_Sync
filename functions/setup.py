import json
import logging
from typing import Dict, List
from functions.http_requests import get_request
from classes.Data import SignBoxPlaceholder
import os



# Required keys for the configuration
required_keys: List[str] = [
    "api_key",
    "organization_id",
    "workspace_id",
    "endpoint",
    "folder_path",
    "file_log_path",
    "destination_path",
]
params: Dict[str, str] = {}


def read_config(file_path: str) -> Dict[str, str]:
    """
    Read the configuration from a JSON file.

    :param file_path: Path to the JSON configuration file.
    :return: Configuration as a dictionary.
    """
    with open(file_path, "r") as file:
        config = json.load(file)
    return config


def read_signbox_map(file_path: str) -> Dict[str, SignBoxPlaceholder]:
    """
    Reads the signbox_map.json file and returns its content as a Python dictionary,
    parsing the values into SignBoxPlaceholder objects.

    Args:
        file_path (str): The path to the signbox_map.json file.

    Returns:
        dict: A dictionary containing the signbox map data with SignBoxPlaceholder objects.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        signbox_map_raw = json.load(file)

    signbox_map = {
        key: SignBoxPlaceholder(**value) for key, value in signbox_map_raw.items()
    }
    return signbox_map


def read_user_map(file_path: str) -> Dict[str, int]:
    """
    Reads the user_map.json file and returns its content as a Python dictionary.

    Args:
        file_path (str): The path to the user_map.json file.

    Returns:
        dict: A dictionary containing the user map data.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        user_map = json.load(file)
    return user_map


def check_params() -> None:
    """
    Check if the configuration contains all required keys.

    :param config: Configuration dictionary.
    :param required_keys: List of required keys.
    :raises KeyError: If a required key is missing.
    """
    for key in required_keys:
        if key not in params:
            raise KeyError(f"Missing required key: {key}")


def api_check(endpoint: str, headers: Dict[str, str]) -> None:
    """
    Call a set of APIs to check the connection with the API client.

    :param endpoint: URL of the API endpoint.
    :param headers: Dictionary of headers to include in the request
    """
    logging.info("Getting Server Timestamp")
    ping_response = get_request(f"{endpoint}/ping", headers=headers)
    logging.info(f"Server Timestamp: {ping_response.content}")

    logging.info("Getting User Information")
    whoami_response = get_request(f"{endpoint}/whoami", headers=headers)
    user_info = whoami_response.json()
    logging.info(f"You're logged in as: {user_info['name']} {user_info['surname']}")


def setup_logging(log_file: str) -> None:
    """
    Set up logging to log messages to both a file and the console.

    :param log_file: The file to which logs will be written.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )


    # functions/setup.py

def setup() -> Dict[str, str]:
    """
    Legge la configurazione dal file db_config.json e ritorna un dizionario con i parametri.
    Compatibile con sql_reader.py e flussi di test.

    :return: Dizionario con parametri, es. {'connection_string': '...'}
    """
    try:
        project_root = os.path.abspath(os.path.dirname(__file__))
        db_config_path = os.path.join(project_root, "data", "db_config.json")

        # Se il file non esiste, prova a risalire alla cartella principale del progetto
        if not os.path.exists(db_config_path):
            db_config_path = os.path.join(project_root, "..", "data", "db_config.json")

        with open(db_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if "connection_string" not in config:
            raise KeyError("'connection_string' non trovato in db_config.json")

        return config

    except Exception as e:
        logging.error(f"Errore nel leggere setup: {e}")
        return {}
