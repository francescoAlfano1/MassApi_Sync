import logging
import requests
import time
from functools import wraps
from typing import Callable, Any, Dict

# --- Variabili globali configurabili ---
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.0
RETRYABLE_STATUSES = (500, 502, 503, 504)
API_CALL_DELAY = 0.5

def http_request(func: Callable[..., requests.Response]) -> Callable[..., Any]:
    """
    Decorator robusto per gestire richieste HTTP con retry, backoff e logging.
    Garantisce che risposte valide (200/201/204) non vengano mai restituite come None.
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        attempt = 0

        while attempt <= MAX_RETRIES:
            try:
                response = func(*args, **kwargs)

                if response is None:
                    raise requests.exceptions.RequestException("Response is None")

                status = response.status_code

                # Se NON è retryable → ritorna sempre la response
                if status not in RETRYABLE_STATUSES:
                    if 400 <= status < 500 and status != 409:
                        response.raise_for_status()

                    time.sleep(API_CALL_DELAY)
                    return response

                # Status retryable → retry
                logging.warning(
                    f"[Tentativo {attempt+1}/{MAX_RETRIES}] "
                    f"Status {status} da {func.__name__} → retry"
                )

            except requests.exceptions.RequestException as e:
                logging.error(
                    f"[Tentativo {attempt+1}/{MAX_RETRIES}] Errore chiamata {func.__name__}:\n"
                    f"\tURL: {args[0]}\n"
                    f"\tKwargs: {kwargs}\n"
                    f"\tError: {e}"
                )

            attempt += 1
            if attempt <= MAX_RETRIES:
                sleep_time = BACKOFF_FACTOR * (2 ** (attempt - 1))
                logging.info(f"Attendo {sleep_time:.1f}s prima del retry...")
                time.sleep(sleep_time)

        logging.critical(
            f"Tutti i {MAX_RETRIES} tentativi falliti per {func.__name__} "
            f"→ nessuna risposta valida da {args[0]}"
        )
        return None

    return wrapper


# --- FUNZIONI HTTP ESPORTE ---
@http_request
def get_request(url: str, headers: Dict[str, str], **kwargs) -> requests.Response:
    return requests.get(url, headers=headers, **kwargs)

@http_request
def post_request(url: str, headers: Dict[str, str], **kwargs) -> requests.Response:
    return requests.post(url, headers=headers, **kwargs)

@http_request
def put_request(url: str, headers: Dict[str, str], **kwargs) -> requests.Response:
    return requests.put(url, headers=headers, **kwargs)
