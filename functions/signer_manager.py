import logging
from functions.http_requests import get_request, post_request, put_request


# ==============================================================================
# FILE: signer_manager.py
# SCOPO:
#   Sincronizzazione completa dei firmatari (external user) con Contract Geek.
#
# VERSIONE:
#   Dicembre 2025 — Versione definitiva con:
#     • struttura finale firmatari (record + workspaces)
#     • GET cross-workspace per ottenere ID
#     • POST/PUT con Workspace-ID = "0"
#     • UNA sola associazione firmatario–controparte (cross-workspace)
#     • commenti estesi per massima leggibilità
#
# NOTA IMPORTANTE:
#   La distinzione external/natural esiste solo nel DB.
#   Tutti i firmatari vengono sincronizzati tramite API external user:
#
#       POST /Controparte/User
#       PUT  /Controparte/User
#       POST /Controparte/{id_controparte}/User/{user_id}
#
#   Workspace-ID = "0" è valido e corretto per:
#       • GET utenti
#       • GET controparti
#       • POST/PUT utenti
#       • POST associazione firmatario–controparte
#
#   L’associazione è cross-workspace → NON serve farla per ogni workspace.
# ==============================================================================



# ==============================================================================
# 1. CARICAMENTO FIRMATARI REMOTI (VERSIONE ESTESA: MAIL + CF)
# ==============================================================================

def load_remote_signers(endpoint: str, headers: dict) -> dict:
    """
    Carica TUTTI i firmatari presenti su Contract Geek, indicizzati sia per mail
    che per codice fiscale. Questo permette di intercettare firmatari che hanno
    cambiato mail ma mantengono lo stesso CF.

    OUTPUT:
        {
            "by_mail": {
                "email_normalizzata": {
                    "user_id": <int>,
                    "mail": "...",
                    "cf": "...",
                    "controparti_ids": [...]
                }
            },
            "by_cf": {
                "CF_NORMALIZZATO": {
                    "user_id": <int>,
                    "mail": "...",
                    "cf": "...",
                    "controparti_ids": [...]
                }
            }
        }
    """
    logging.error(">>> VERSIONE NUOVA DI load_remote_signers ATTIVA <<<")

    url = f"{endpoint}/Controparte/User"

    ws_headers = headers.copy()
    ws_headers["Workspace-ID"] = "0"

    response = get_request(url, ws_headers)

    signer_by_mail = {}
    signer_by_cf = {}

    if response and response.status_code == 200:
        for s in response.json():

            email = (s.get("mail") or "").strip().lower()
            cf = (s.get("cf") or "").strip().upper()

            entry = {
                "user_id": s.get("user_id"),
                "mail": email,
                "cf": cf,
                "controparti_ids": s.get("controparte_ids", [])
            }

            # Indicizzazione per mail
            if email:
                signer_by_mail[email] = entry

            # Indicizzazione per CF
            if cf:
                signer_by_cf[cf] = entry

    else:
        logging.error(
            f"[REMOTE SIGNERS] Errore GET /Controparte/User: "
            f"{response.text if response else 'nessuna risposta'}"
        )

    logging.info(
        f"[REMOTE SIGNERS] Trovati {len(signer_by_mail)} firmatari remoti "
        f"(indicizzati per mail) e {len(signer_by_cf)} per CF."
    )

    return {
        "by_mail": signer_by_mail,
        "by_cf": signer_by_cf
    }





# ==============================================================================
# 2. ASSOCIAZIONE FIRMATARIO → CONTROPARTE (CROSS-WORKSPACE)
# ==============================================================================
def associate_signer_to_client(
    user_id: int,
    controparte_id: int,
    endpoint: str,
    headers: dict
):
    """
    Associa un firmatario a una controparte tramite API Contract Geek.
    """

    # Workspace cross-organization
    ws_headers = headers.copy()
    ws_headers["Workspace-ID"] = "0"

    url = f"{endpoint}/Controparte/{controparte_id}/User/{user_id}"

    # Effettuo la POST di associazione
    resp = post_request(url, headers=ws_headers, json={})

    # -----------------------------
    # Gestione status code
    # -----------------------------
    if resp and resp.status_code == 204:
        logging.info(
            f"[ASSOC] OK → user {user_id} associato a controparte {controparte_id}"
        )

    elif resp and resp.status_code == 409:
        logging.info(
            f"[ASSOC] Già associato → user {user_id} ↔ controparte {controparte_id}"
        )

    elif resp and resp.status_code == 403:
        logging.error(
            f"[ASSOC] 403 Forbidden → user {user_id} ↔ controparte {controparte_id} "
            f"(probabile controparte non accessibile nell'organizzazione)"
        )

    elif resp and resp.status_code == 404:
        logging.error(
            f"[ASSOC] 404 Not Found → controparte {controparte_id} non trovata"
        )

    else:
        logging.error(
            f"[ASSOC] Errore generico associando user {user_id} ↔ controparte {controparte_id}: "
            f"{resp.text if resp else 'nessuna risposta'}"
        )

    # Ritorno SEMPRE la response HTTP completa
    return resp


# ==============================================================================
# 3. ASSOCIAZIONE MULTI-CONTROPARTE (UNA POST PER CONTROPARTE)
# ==============================================================================
def ensure_signer_associated_to_all_clients(
    user_id: int,
    record_firmatario: dict,
    controparti_map_all: dict,
    endpoint: str,
    headers: dict,
    summary: dict | None = None
) -> None:
    """
    Associa un firmatario a tutte le controparti collegate,
    evitando associazioni duplicate o impossibili.
    """

    email = record_firmatario.get("mail", "")
    cont_keys = record_firmatario.get("controparti_keys", []) or []

    if not cont_keys:
        logging.info(f"[ASSOC] Nessuna controparti_keys per {email}, salto.")
        return

    # Se il firmatario è stato appena creato con controparte_ids,
    # l'associazione è già stata fatta dal POST iniziale.
    created_with_ids = record_firmatario.get("_created_with_ids", False)

    for key in cont_keys:
        if not key:
            continue

        # 1️⃣ Risolvo id_controparte
        id_controparte = None
        for ws_id, cont_map in controparti_map_all.items():
            cont_ids = cont_map.get(key)
            if cont_ids:
                id_controparte = cont_ids[0]
                break

        if not id_controparte:
            logging.warning(
                f"[ASSOC] Controparte '{key}' non trovata nei workspace (firmatario {email}). Ignoro."
            )
            continue

        # 2️⃣ Se il firmatario è stato creato con controparte_ids → skip
        if created_with_ids:
            logging.info(
                f"[ASSOC] Skip associazione {email} ↔ {id_controparte}: "
                f"già associato tramite POST di creazione."
            )
            continue

        # 3️⃣ POST di associazione
        resp = associate_signer_to_client(
            user_id=user_id,
            controparte_id=id_controparte,
            endpoint=endpoint,
            headers=headers
        )

        # 4️⃣ Gestione risultati
        if not resp:
            logging.error(
                f"[ASSOC] Nessuna risposta associando {email} ↔ {id_controparte}"
            )
            continue

        if resp.status_code == 204:
            logging.info(f"[ASSOC] ✔ Associato {email} ↔ {id_controparte}")
            if summary is not None:
                summary["associations"].append({
                    "mail": email,
                    "controparte_id": id_controparte,
                    "status": "associated"
                })

        elif resp.status_code == 409:
            logging.info(f"[ASSOC] ↺ Già associato {email} ↔ {id_controparte}")
            if summary is not None:
                summary["associations"].append({
                    "mail": email,
                    "controparte_id": id_controparte,
                    "status": "already_associated"
                })

        elif resp.status_code == 403:
            logging.warning(
                f"[ASSOC] ⚠ 403 Forbidden: {email} ↔ {id_controparte} "
                f"(probabile controparte di altra Organization-ID)"
            )

        elif resp.status_code == 404:
            logging.warning(
                f"[ASSOC] ⚠ 404 Controparte {id_controparte} inesistente per {email}"
            )

        else:
            logging.error(
                f"[ASSOC] ✘ Errore {resp.status_code} associando {email} ↔ {id_controparte}: {resp.text}"
            )



# ==============================================================================
# 4. CREAZIONE/AGGIORNAMENTO FIRMATARIO (EXTERNAL USER) — VERSIONE DEFINITIVA
# ==============================================================================

# ==============================================================================
# 4. CREAZIONE/AGGIORNAMENTO FIRMATARIO (EXTERNAL USER) — VERSIONE DEFINITIVA
# ==============================================================================

def sync_external_signer(
    record_firmatario: dict,
    remote_signers: dict,
    controparti_map_all: dict,
    endpoint: str,
    headers: dict,
    summary: dict | None = None
) -> int | None:
    """
    Sincronizza un firmatario (external user) con Contract Geek.

    Logica estesa:
        • Ricerca primaria per mail
        • Ricerca secondaria per CF (per intercettare cambi mail)
        • Se trovato per CF → aggiorna mail tramite PUT
        • Se NON trovato → POST creazione
        • Se esiste → associa controparti mancanti + PUT finale
    """

    # ----------------------------------------------------------------------
    # 1️⃣ VALIDAZIONE EMAIL
    # ----------------------------------------------------------------------
    email = record_firmatario.get("mail")
    if not email:
        logging.warning(f"[SYNC] Firmatario senza email, salto: {record_firmatario}")
        return None

    email_key = email.strip().lower()
    cf_key = (record_firmatario.get("cf") or "").strip().upper()

    remote_by_mail = remote_signers.get("by_mail", {})
    remote_by_cf = remote_signers.get("by_cf", {})

    # ----------------------------------------------------------------------
    # 2️⃣ RICERCA PRIMARIA PER MAIL
    # ----------------------------------------------------------------------
    remote_info = remote_by_mail.get(email_key)

    # ----------------------------------------------------------------------
    # 3️⃣ RICERCA SECONDARIA PER CF (MAIL CAMBIATA)
    # ----------------------------------------------------------------------
    if not remote_info and cf_key:
        remote_info = remote_by_cf.get(cf_key)
        if remote_info:
            logging.info(f"[SYNC] Firmatario trovato tramite CF: {cf_key}")

            # Aggiorno la mail tramite PUT
            payload_put = {
                "id": remote_info["user_id"],
                "mail": email_key,
                "name": record_firmatario.get("name", ""),
                "surname": record_firmatario.get("surname", ""),
                "phone": record_firmatario.get("phone", ""),
                "cf": cf_key,
                "metadata": record_firmatario.get("metadata", '{"sync":"auto"}'),
                "accountType": 0
            }

            put_request(f"{endpoint}/Controparte/User", headers=headers, json=payload_put)

            # Aggiorno le mappe remote (mail + CF) in modo coerente
            entry = {
                "user_id": remote_info["user_id"],
                "mail": email_key,
                "cf": cf_key,
                "controparti_ids": remote_info.get("controparti_ids", [])
            }
            remote_by_mail[email_key] = entry
            remote_by_cf[cf_key] = entry

    # ----------------------------------------------------------------------
    # 4️⃣ USER_ID FINALE DOPO LE RICERCHE
    # ----------------------------------------------------------------------
    remote_info = remote_by_mail.get(email_key)
    user_id = remote_info["user_id"] if remote_info else 0

    # ----------------------------------------------------------------------
    # 5️⃣ RISOLUZIONE CONTROPARTI
    # ----------------------------------------------------------------------
    resolved_ids = []
    for key in record_firmatario.get("controparti_keys", []):
        for ws_map in controparti_map_all.values():
            if key in ws_map:
                resolved_ids.append(ws_map[key][0])
                break

    if not resolved_ids:
        logging.warning(f"[SYNC] Nessuna controparte valida trovata per {email_key}")
        resolved_ids = []

    # ----------------------------------------------------------------------
    # 6️⃣ CASO A: FIRMATARIO NON ESISTE → POST CREAZIONE
    # ----------------------------------------------------------------------
    if not user_id:
        logging.info(f"[SYNC] POST creazione firmatario {email_key}")

        payload = {
            "user_id": 0,
            "mail": email_key,
            "name": record_firmatario.get("name", ""),
            "surname": record_firmatario.get("surname", ""),
            "phone": record_firmatario.get("phone", ""),
            "cf": cf_key,
            "metadata": record_firmatario.get("metadata", '{"sync":"auto"}'),
            "controparte_ids": resolved_ids
        }

        resp = post_request(f"{endpoint}/Controparte/User", headers=headers, json=payload)

        if resp and resp.status_code in (200, 201):
            new_id = resp.json().get("user_id")
            if new_id:
                record_firmatario["_created_with_ids"] = True
                entry = {
                    "user_id": new_id,
                    "mail": email_key,
                    "cf": cf_key,
                    "controparti_ids": resolved_ids
                }
                remote_by_mail[email_key] = entry
                if cf_key:
                    remote_by_cf[cf_key] = entry
                logging.info(f"[SYNC] Firmatario creato con ID {new_id}")
                if summary is not None:
                    summary["created"].append({
                        "mail": email_key,
                        "user_id": new_id
                    })
                return new_id

        elif resp and resp.status_code == 202:
            logging.info(f"[SYNC] 202 → firmatario {email_key} già presente, recupero ID")
            refreshed_all = load_remote_signers(endpoint, headers)
            refreshed = refreshed_all["by_mail"].get(email_key)

            if refreshed:
                return refreshed["user_id"]

        elif resp and resp.status_code == 409:
            logging.error(f"[SYNC] 409 → firmatario {email_key} associato ad altra organizzazione")
            return None

        else:
            logging.error(f"[SYNC] Errore POST firmatario {email_key}: {resp.text if resp else 'nessuna risposta'}")
            return None

    # ----------------------------------------------------------------------
    # 7️⃣ CASO B: FIRMATARIO ESISTE → ASSOCIAZIONI + PUT FINALE
    # ----------------------------------------------------------------------
    logging.info(f"[SYNC] Firmatario esistente {email_key} (ID {user_id})")

    ensure_signer_associated_to_all_clients(
        user_id=user_id,
        record_firmatario=record_firmatario,
        controparti_map_all=controparti_map_all,
        endpoint=endpoint,
        headers=headers,
        summary=summary
    )

    logging.info(f"[SYNC] PUT finale firmatario {email_key} (ID {user_id})")

    payload_put = {
        "id": user_id,
        "mail": email_key,
        "name": record_firmatario.get("name", ""),
        "surname": record_firmatario.get("surname", ""),
        "phone": record_firmatario.get("phone", ""),
        "cf": cf_key,
        "metadata": record_firmatario.get("metadata", '{"sync":"auto"}'),
        "accountType": 0
    }

    resp = put_request(f"{endpoint}/Controparte/User", headers=headers, json=payload_put)

    if not resp or resp.status_code != 204:
        logging.warning(
            f"[SYNC] Errore PUT finale firmatario {email_key}: "
            f"{resp.text if resp else 'nessuna risposta'}"
        )
    else:
        entry = {
            "user_id": user_id,
            "mail": email_key,
            "cf": cf_key,
            "controparti_ids": resolved_ids
        }
        remote_by_mail[email_key] = entry
        if cf_key:
            remote_by_cf[cf_key] = entry
        if summary is not None:
            summary["updated"].append({
                "mail": email_key,
                "user_id": user_id
            })

    return user_id



# ==============================================================================
# 5. SYNC COMPLETO DI TUTTI I FIRMATARI  ()
# ==============================================================================
def sync_all_signers(
    final_users: dict,
    controparti_map_all: dict,
    endpoint: str,
    headers: dict
):
    """
    Sincronizza TUTTI i firmatari usando la struttura finale:

        {
          "mail|CF": {
            "record": {
                "mail": "...",
                "name": "...",
                "surname": "...",
                "phone": "...",
                "cf": "...",
                "metadata": "...",
                "controparti_keys": [...]
            }
          }
        }

    Logica:
        1. Carico firmatari remoti
        2. Per ogni firmatario logico:
            - sync_external_signer(record)
            - ricarico remote_signers per evitare duplicati e 202
        3. Ritorno la mappa aggiornata dei firmatari remoti + summary
    """

    # ============================================================
    # SUMMARY STRUTTURATO ()
    # ============================================================
    summary = {
        "created": [],       # firmatari creati
        "updated": [],       # firmatari aggiornati
        "associations": [],  # associazioni firmatario ↔ controparte
        "errors": []         # errori
    }

    remote_signers = load_remote_signers(endpoint, headers)
    logging.info(f"[SYNC ALL] Inizio sincronizzazione firmatari: {len(final_users)} totali")

    for key, user_struct in final_users.items():
        record = user_struct["record"]
        email = record.get("mail", "").lower()

        logging.info(f"[SYNC ALL] → Sync firmatario {email}")

        try:
            sync_external_signer(
                record_firmatario=record,
                remote_signers=remote_signers,
                controparti_map_all=controparti_map_all,
                endpoint=endpoint,
                headers=headers,
                summary=summary
            )

            #  Ricarico firmatari remoti per evitare duplicati e 202
            remote_signers = load_remote_signers(endpoint, headers)

        except Exception as e:
            logging.error(
                f"[SYNC ALL] Errore sincronizzando firmatario {email}: {e}",
                exc_info=True
            )
            summary["errors"].append({
                "mail": email,
                "error": str(e)
            })

    logging.info("[SYNC ALL] Sincronizzazione firmatari completata.")

    #  ORA RITORNA ANCHE IL SUMMARY 
    return remote_signers, summary


# ==============================================================================
# EXTRA --- per test final structure ma anche per flusso completo.
# ==============================================================================

def group_users_by_key(users_raw: dict) -> dict:
    final = {}

    all_users = users_raw.get("externals", []) + users_raw.get("naturals", [])

    for u in all_users:
        mail = (u.get("mail") or "").strip().lower()
        cf = (u.get("cf") or "").strip().upper()
        piva_azienda = (u.get("piva") or u.get("piva_azienda") or "").strip()

        if not mail or not cf:
            continue

        key = f"{mail}|{cf}"

        # lista di controparti dalla riga sorgente
        cont_keys = u.get("controparti_keys", [])

        # --- NUOVA LOGICA: determinazione chiave controparte ---
        resolved_keys = []

        # 1. Se il firmatario ha una PIVA aziendale → usa quella
        if piva_azienda:
            resolved_keys.append(piva_azienda)

        # 2. Altrimenti, se non c’è PIVA → usa il CF
        elif cf:
            resolved_keys.append(cf)

        # 3. Aggiungi eventuali controparti_keys già presenti nella sorgente
        for ck in cont_keys:
            if ck and ck not in resolved_keys:
                resolved_keys.append(ck)

        # ---------------------------------------------------------

        if key not in final:
            final[key] = {
                "record": {
                    "mail": mail,
                    "name": u.get("name", ""),
                    "surname": u.get("surname", ""),
                    "phone": u.get("phone", ""),
                    "cf": cf,
                    "metadata": u.get("metadata", '{"sync":"auto"}'),
                    "controparti_keys": []
                }
            }

        # accumulo tutte le controparti_keys risolte
        for ck in resolved_keys:
            if ck and ck not in final[key]["record"]["controparti_keys"]:
                final[key]["record"]["controparti_keys"].append(ck)

    return final


