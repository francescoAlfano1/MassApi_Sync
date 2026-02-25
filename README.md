# 📑  Mass Workflow & User Sync con WebApp di Contract Geek
**Documentazione tecnica completa** | Ultimo aggiornamento: 30/12/2025

---

## 1. Panoramica generale

Il progetto è composto da due flussi principali, indipendenti ma coordinati tramite configurazioni, mapping e moduli condivisi.

| Flusso | Descrizione | Entrypoint |
|--------|-------------|------------|
| Workflow PDF / Firma elettronica | Automatizza scansione, elaborazione e invio PDF a Contract Geek per firma elettronica. Gestisce posizioni dei campi di firma, avanzamento workflow, gestione esiti. | `main.py` |
| Sincronizzazione Controparti & Firmatari | Legge controparti e firmatari da SQL Server e li sincronizza con Contract Geek tramite API REST. Gestisce logica multi workspace e associazioni Controparte–Firmatari. | `main_user_sync.py` |

### Moduli condivisi principali

- **`functions/http_requests.py`** — Wrapper robusto per chiamate API (GET / POST / PUT) con:
  - retry intelligente
  - gestione status code (200/201/202/4xx/5xx)
  - logging dettagliato request/response (senza loggare dati sensibili inutilmente)

- **`functions/setup.py`**
  - Lettura configurazioni (`config.json`, `db_config.json`)
  - Test di reachability API (es. ping, check key, organization)
  - Setup logging minimo in fasi iniziali

- **`functions/logger_setup.py`**
  - Configurazione logging centralizzato: file giornaliero, output console, formattazione uniforme

### Schedulazione

- `main.py` → ogni 5 minuti (gestione workflow PDF)
- `main_user_sync.py` → ogni notte (sync controparti + firmatari)
  - se fallisce, viene rieseguito al ciclo successivo
  - `data/last_user_sync.txt` registra l'ultima esecuzione completata con successo (timestamp)

---

## 2. Architettura e struttura file

```
project_root/
├── main.py                       # Workflow PDF/Firme
├── main_user_sync.py             # Sync controparti + firmatari
├── data/
│   ├── config.json               # Configurazione API
│   ├── db_config.json            # Configurazione SQL Server
│   ├── signbox_map.json          # (se usato) mapping per workflow
│   ├── user_map.json             # (eventuale) mapping utente locale/remote
│   ├── workspace_map.json        # mapping CodUffServizio → workspace_id API (fondamentale)
│   └── last_user_sync.txt        # timestamp ultima sync utenti/controparti
├── functions/
│   ├── setup.py
│   ├── logger_setup.py
│   ├── http_requests.py
│   ├── sql_reader.py
│   ├── workflow_manager.py
│   ├── client_manager.py
│   ├── signer_manager.py
├── test_api_calls.py
├── test_sql_reader.py
├── test_final_structure.py
├── manual_test_client_sync.py
├── test_signer_manager.py
├── Massiva_manual_test_client_sync.py
├── Massiva_test_signer_manager.py
```

---

## 3. Configurazione

### `config.json`
Parametri generali per le API Contract Geek:
- `api_key`
- `endpoint` (base URL)
- `organization_id`
- `workspace_id` (workspace di default, usato solo dove serve)

### `db_config.json`
Parametri connessione SQL Server:
- `host`, `database`, `user`, `password`
- altre impostazioni specifiche (timeout, ecc.)

### `workspace_map.json`
Mapping fondamentale per la logica multi workspace.
- chiave: `CodUffServizio` (logico, es. `"001"`)
- valore: `workspace_id` API (numerico, es. `100`)

Esempio:
```json
{
  "001": 100,
  "002": 101,
  "003": 102,
  "004": 103,
  "005": 104
}
```

### `last_user_sync.txt`
Contiene un timestamp (data/ora) dell'ultima sincronizzazione utenti/controparti completata con successo. Può essere usato in futuro per sync incrementali.

---

## 4. Flusso – Sincronizzazione Controparti & Firmatari

**Entrypoint:** `main_user_sync.py`

### Sequenza operativa (alta visione)

1. Caricamento configurazioni (API + DB)
2. Setup logging centralizzato
3. Test API (`setup.api_check()`)
4. Lettura dati dal DB (`sql_reader`)
   - `fetch_clients()` → controparti (multi workspace)
   - `fetch_users()` → firmatari con controparti collegate
5. Costruzione struttura finale (logica dati)
   - `group_clients_by_key()` in `client_manager.py`
   - `group_users_by_key()` in `signer_manager.py`
6. Sincronizzazione controparti (`sync_all_clients()` in `client_manager.py`)
7. Sincronizzazione firmatari (`sync_all_signers()` in `signer_manager.py`)
8. Aggiornamento `last_user_sync.txt`
9. Logging dettagliato + riepilogo finale

---

## 5. Logica funzionale

### ⭐ Premessa fondamentale: come ragiona Contract Geek

- Una Controparte appartiene all'Organizzazione, ma la sua visibilità/gestione dipende dai Workspace.
- Una Controparte può esistere a livello organizzativo, ma se non è associata a un certo workspace:
  - non puoi modificarla da quel workspace
  - non puoi associarle firmatari in quel workspace
  - alcune API rispondono con 403/409
- Per questo esiste la chiamata:

```
POST /Controparte/{id}/workspace/{workspace_id}
```

Serve per:
- "agganciare" una controparte pre-esistente a un workspace specifico
- permettere PUT/associazioni in quel workspace
- evitare errori 403/409 quando la controparte non è ancora agganciata

### ⭐ La sorgente dati è multi workspace

Esempio controparti:
```
EXAMPLE S.R.L. | PIVA 12345678901 | workspace_logico 003
EXAMPLE S.R.L. | PIVA 12345678901 | workspace_logico 002
```
- Stessa PIVA → stessa controparte logica
- Deve esistere su più workspace contemporaneamente (003, 002)

Esempio firmatari:
```
MARIO ROSSI | mail mario.rossi@example.com | CF RSSMRA80A01H501Z | workspace_logico 001
MARIO ROSSI | mail mario.rossi@example.com | CF RSSMRA80A01H501Z | workspace_logico 002
MARIO ROSSI | mail mario.rossi@example.com | CF RSSMRA80A01H501Z | workspace_logico 003
```
- Stessa mail + CF → stesso firmatario logico
- Deve esistere su più workspace (001, 002, 003)

### ⭐ Logica corretta per le Controparti (implementata)

Per ogni controparte logica (identificata da PIVA/CF):

1. **Raggruppamento dati di sorgente** — Dal DB arrivano più righe (una per workspace logico). Vengono raggruppate in un unico record logico con dati anagrafici unici e lista di workspace API in cui deve esistere.

2. **Ricerca Controparte remota** — Si costruisce una mappa delle controparti già presenti su Contract Geek, per workspace (`GET /Controparte` per ogni workspace). Si risale a: id controparte e in quali workspace è già agganciata.

3. **Confronto workspace richiesti vs attuali** — Sorgente dati (es. 001, 002, 003) → tradotti in workspace API (es. 100, 101, 102). Workspace attuali (da API) → elenco workspace in cui la controparte è già presente.

4. **Creazione o individuazione Controparte**
   - Se non esiste la controparte (per quella PIVA/CF) in nessun workspace → `POST /Controparte` nel primo workspace della lista
   - Se esiste → recupero il suo id

5. **Aggancio ai workspace mancanti**
   ```
   POST /Controparte/{id}/workspace/{workspace_id}
   ```

6. **Aggiornamento dati (PUT)**
   ```
   PUT /Controparte/{id}
   ```
   Serve ad allineare mail, PEC, indirizzo, telefono, nazione, ecc.

7. **Preparazione per i firmatari** — La mappa controparti (id + workspace) viene salvata in memoria e passata alla logica dei firmatari.

---

### ⭐ Firmatari — Logica definitiva

1. **Verifica esistenza firmatario**
   ```
   GET /Controparte/User
   Workspace-ID: "0"
   ```

2. Se esiste → ignorare completamente i workspace

3. **Determinare controparti già associate**
   ```
   GET /Controparte/{id_controparte}/User
   ```

4. **Determinare controparti mancanti** — Differenza tra `controparti_keys` locali e controparti associate su Contract Geek.

5. Se il firmatario ESISTE → **MAI** fare POST di creazione

6. **Associare solo le controparti mancanti**
   ```
   POST /Controparte/{id_controparte}/User/{user_id}
   Workspace-ID: "0"
   ```

7. Se il firmatario è completo → fare solo PUT
   ```
   PUT /Controparte/User
   ```

8. Se NON esiste → creazione + associazione in un colpo solo
   ```json
   POST /Controparte/User
   {
     "user_id": 0,
     "mail": "...",
     "name": "...",
     "surname": "...",
     "phone": "...",
     "cf": "...",
     "controparte_ids": [id1, id2, ...],
     "metadata": "..."
   }
   ```

### Riepilogo operativo

| Caso | Azione |
|------|--------|
| Firmatario NON esiste | POST con tutte le controparti |
| Firmatario ESISTE ma mancano controparti | POST associazione singola |
| Firmatario ESISTE ed è completo | PUT |
| POST ritorna 202 | recupero ID → PUT |

**Nuova logica corretta:**
- UNA POST per ogni controparte
- Workspace-ID = "0"
- nessun ciclo sui workspace
- nessuna intersect workspace

---

## 6. Dettaglio moduli tecnici

### 6.1 `client_manager.py`

**Funzioni principali:**

- **Caricamento workspace disponibili** — `GET /Organization/Workspace` → costruisce mappa `workspace_id → metadata`
- **Caricamento controparti remote per workspace** — `GET /Controparte` per ogni workspace attivo
- **`group_clients_by_key(clients: list) -> dict`** — raggruppa per PIVA/CF, costruisce struttura finale:

```json
"12345678901": {
  "record": {
    "controparte_name": "...",
    "controparte_piva": "12345678901",
    "controparte_cf": "0000012345678901",
    "controparte_city": "...",
    "controparte_address": "...",
    "controparte_mail": "...",
    "controparte_pec": "...",
    "controparte_phone": "...",
    "key": "12345678901"
  },
  "workspaces": ["100", "101", "102"]
}
```

- **Creazione nuova Controparte** — `POST /Controparte` nel primo workspace della lista
- **Aggiornamento Controparte** — `PUT /Controparte/{id}` dopo l'aggancio ai workspace mancanti
- **Aggiunta ai workspace mancanti** — `POST /Controparte/{id}/workspace/{workspace_id}`
- **`sync_all_clients()`** — cicla su tutte le controparti, applica la logica, restituisce mappa completa

### 6.2 `signer_manager.py` — Modello unificato

| Funzione | Stato | Descrizione |
|----------|-------|-------------|
| `load_remote_signers()` | invariata | Carica firmatari remoti |
| `create_signer()` | nuova | POST creazione con `controparte_ids` |
| `update_signer()` | nuova | PUT aggiornamento |
| `is_signer_associated_to_controparte()` | nuova | `GET /Controparte/{id}/User` |
| `associate_signer_to_client()` | invariata | POST associazione |
| `ensure_signer_associated_to_all_clients()` | aggiornata | UNA POST per controparte |
| `sync_external_signer()` | riscritta | Implementa il flusso corretto |
| `sync_all_signers()` | aggiornata | Ricarica `remote_signers` dopo ogni sync |

**Premessa:** i firmatari NON hanno logica multi workspace. `Workspace-ID` è sempre `"0"` per tutte le API firmatari. La visibilità è derivata dalle controparti associate.

### 6.3 `sql_reader.py`

**`fetch_clients()`** — Legge controparti multi workspace dal DB. Output esempio:

```json
{
  "controparte_name": "EXAMPLE S.R.L.",
  "controparte_piva": "12345678901",
  "controparte_cf": "0000012345678901",
  "controparte_city": "MILANO",
  "controparte_address": "VIA ROMA 1",
  "controparte_mail": "info@example.com",
  "controparte_pec": "example@legalmail.it",
  "controparte_phone": "0212345678",
  "workspace_id": 100,
  "workspace_logico": "001",
  "key": "12345678901"
}
```

**`fetch_users()`** — Legge firmatari dal DB (multi workspace). Classifica external vs natural. Output:

```python
{
  "externals": [ ... lista firmatari external grezzi ... ],
  "naturals":  [ ... lista firmatari natural grezzi ... ]
}
```

---

## 7. `main_user_sync.py` (orchestratore)

### Sequenza corretta

1. Carica configurazioni (API + DB)
2. Setup logging centralizzato
3. Test API (ping, organization, ecc.)
4. Legge dati dal DB: `clients_raw = fetch_clients()`, `users_raw = fetch_users()`
5. Costruisce strutture finali: `final_clients = group_clients_by_key(clients_raw)`, `final_users = group_users_by_key(users_raw)`
6. Esegue sincronizzazione controparti: `controparti_map_all = sync_all_clients(final_clients)`
7. Esegue sincronizzazione firmatari: `sync_all_signers(final_users, controparti_map_all)`
8. Aggiorna `last_user_sync.txt`
9. Logga riepilogo finale

### Gestione errori

- Se fallisce `sync_all_clients()` → `sync_all_signers()` non viene eseguita
- Errori API singoli: loggati con dettagli, il flusso prosegue con altri record

---

## 8. Logging centralizzato

- File giornaliero: `YYYY-MM-DD_sync.log`
- Output su file e console
- Retention: ~30 giorni (configurabile)
- Tutti i moduli usano lo stesso logger

---

## 9. Test e validazione

- **`test_api_calls.py`** — verifica connettività verso Contract Geek, testa endpoint chiave
- **`test_sql_reader.py`** — chiama `fetch_clients()` e `fetch_users()`, verifica mapping e scarto record invalidi
- **`test_final_structure.py`** — costruisce e salva in `data/output_final_structure.json` la struttura finale per validazione
- **`manual_test_client_sync.py`** — test mirato su un sottoinsieme di controparti
- **`test_signer_manager.py`** — test mirato sulla sync dei firmatari
- **`Massiva_manual_test_client_sync.py`** / **`Massiva_test_signer_manager.py`** — prove di carico su dataset ampi

---

## 10. Esempi pratici di flusso

### 10.1 Esempio Controparte

Dati grezzi dal DB (`fetch_clients`) — tre righe, una per workspace logico:
```
EXAMPLE S.R.L. | 12345678901 | 0000012345678901 | MILANO | VIA ROMA 1 | mail | pec | phone | 001
EXAMPLE S.R.L. | 12345678901 | 0000012345678901 | MILANO | VIA ROMA 1 | mail | pec | phone | 002
EXAMPLE S.R.L. | 12345678901 | 0000012345678901 | MILANO | VIA ROMA 1 | mail | pec | phone | 003
```

Traduzione workspace tramite `workspace_map.json`:
```
001 → 100
002 → 101
003 → 102
```

Struttura finale generata da `group_clients_by_key()`:
```json
"12345678901": {
  "record": {
    "controparte_name": "EXAMPLE S.R.L.",
    "controparte_piva": "12345678901",
    "controparte_cf": "0000012345678901",
    "controparte_city": "MILANO",
    "controparte_address": "VIA ROMA 1",
    "controparte_mail": "info@example.com",
    "controparte_pec": "example@legalmail.it",
    "controparte_phone": "0212345678",
    "key": "12345678901"
  },
  "workspaces": ["100", "101", "102"]
}
```

Flusso di sincronizzazione:
1. Ricerca Controparte per PIVA/CF → se non esiste: `POST /Controparte` (es. workspace 100)
2. Recupero workspace attuali → es. la controparte esiste solo su 100
3. Confronto: richiesti 100, 101, 102 → attuali 100 → mancanti: 101, 102
4. Aggancio workspace mancanti: `POST /Controparte/{id}/workspace/101`, `POST /Controparte/{id}/workspace/102`
5. PUT finale: `PUT /Controparte/{id}` per allineare i dati anagrafici

---

### 10.2 Esempio Firmatario

Dati grezzi dal DB (`fetch_users`) — una riga per workspace logico:
```
MARIO ROSSI | mario.rossi@example.com | RSSMRA80A01H501Z | EXAMPLE SRL | 001 | external
MARIO ROSSI | mario.rossi@example.com | RSSMRA80A01H501Z | EXAMPLE SRL | 002 | external
MARIO ROSSI | mario.rossi@example.com | RSSMRA80A01H501Z | EXAMPLE SRL | 003 | external
```

Traduzione workspace:
```
001 → 100
002 → 101
003 → 102
```

Struttura finale generata da `group_users_by_key()`:
```json
"mario.rossi@example.com|RSSMRA80A01H501Z": {
  "record": {
    "mail": "mario.rossi@example.com",
    "name": "MARIO",
    "surname": "ROSSI",
    "phone": "3331234567",
    "cf": "RSSMRA80A01H501Z",
    "controparti_keys": [
      "98765432101"
    ],
    "type": "external"
  },
  "workspaces": ["100", "101", "102"]
}
```

Flusso di sincronizzazione:
1. `GET /Controparte/User` (Workspace-ID: "0") → il firmatario ESISTE o NON ESISTE
2. Se ESISTE → determinazione controparti già associate via `GET /Controparte/{id_controparte}/User`
3. Per ogni controparte mancante: `POST /Controparte/{id_controparte}/User/{user_id}` (Workspace-ID: "0")
4. PUT finale obbligatoria: `PUT /Controparte/User`

---

## 10.5 Errori tipici e gestione

| Errore | Quando accade | Gestione |
|--------|---------------|----------|
| **403** | Controparte non agganciata al workspace | `POST /Controparte/{id}/workspace/{workspace_id}` → ripetere PUT |
| **409** | Controparte già presente nel workspace | Non bloccante, si logga e prosegue |
| **404** | ID non valido o entità cancellata | Log → invalida cache → ricostruisce mappa → ritenta |
| **202** | Creazione asincrona firmatario | Attesa breve → PUT → recupero ID definitivo |
| **400** | Dati invalidi (email, CF, telefono) | Record scartato e loggato, flusso continua |
| **500** | Errore interno Contract Geek | Retry con backoff e logging dettagliato |
| Mapping workspace | `CodUffServizio` non in `workspace_map.json` | Record scartato e loggato |

---

## ⭐ Regola fondamentale (PUT obbligatoria)

La PUT deve essere eseguita **sempre** quando il firmatario ESISTE, anche se già associato a tutte le controparti, perché:
- garantisce allineamento anagrafico
- è idempotente e non crea duplicati
- completa la creazione asincrona dopo un 202
- sincronizza eventuali modifiche lato SQL

### Logica definitiva

**CASO A — Firmatario NON esiste:**
1. `POST /Controparte/User` (con tutte le controparti)
2. Fine (nessuna PUT)

**CASO B — Firmatario ESISTE:**
1. Determino controparti mancanti
2. Se mancano → POST di associazione
3. PUT finale obbligatoria
