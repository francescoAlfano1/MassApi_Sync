# Contract Geek API – Example Responses (Swagger)

---

## GET /Controparte

```bash
curl -X 'GET' \
  'https://api-demo.contractgeek.it/Controparte' \
  -H 'accept: text/plain' \
  -H 'X-api-key: YOUR_API_KEY' \
  -H 'Organization-ID: YOUR_ORGANIZATION_ID' \
  -H 'Workspace-ID: 0'
```

**Request URL**
```
https://api-demo.contractgeek.it/Controparte
```

**Server response – Code 200**

```json
[
  {
    "controparte_id": 1001,
    "controparte_name": "Example Company S.r.l.",
    "controparte_nation": "Italia",
    "controparte_city": "Milano",
    "controparte_mail": "info@example.com",
    "controparte_pec": "example@legalmail.it",
    "controparte_address": "Via Roma 1",
    "controparte_phone": "0212345678",
    "controparte_last_edit": "2025-01-01T10:00:00.000000+00:00",
    "controparte_piva": "12345678901",
    "controparte_webpage": "",
    "controparte_type": 0,
    "controparte_cf": "12345678901"
  },
  {
    "controparte_id": 1002,
    "controparte_name": "Another Company S.r.l.",
    "controparte_nation": "Italia",
    "controparte_city": "Roma",
    "controparte_mail": "info@anothercompany.com",
    "controparte_pec": "",
    "controparte_address": "Via Milano 2",
    "controparte_phone": "",
    "controparte_last_edit": "2025-01-02T10:00:00.000000+00:00",
    "controparte_piva": "98765432101",
    "controparte_webpage": "",
    "controparte_type": 0,
    "controparte_cf": null
  },
  {
    "controparte_id": 1003,
    "controparte_name": "string",
    "controparte_nation": "string",
    "controparte_city": "string",
    "controparte_mail": "string",
    "controparte_pec": "string",
    "controparte_address": "string",
    "controparte_phone": "string",
    "controparte_last_edit": "2025-01-03T10:00:00.000000+00:00",
    "controparte_piva": "string",
    "controparte_webpage": "string",
    "controparte_type": 0,
    "controparte_cf": "string"
  }
]
```

**Response headers**
```
content-type: application/json; charset=utf-8
date: Wed, 01 Jan 2025 10:00:00 GMT
server: nginx
transfer-encoding: chunked
```

---

## Osservazioni

La risposta `GET /Controparte` conferma che l'endpoint restituisce un array di oggetti "controparte"
con tutti i dati essenziali (ID, nome, P.IVA, CF, indirizzo, ecc.).

Possiamo quindi usarla in modo ottimale per recuperare tutte le controparti già presenti nel workspace,
memorizzarle localmente (ad esempio un dizionario `piva → id` o `cf → id`) e poi evitare chiamate
multiple durante la sincronizzazione.

---

## GET /Controparte/User

Il codice di risposta è sempre 200 e l'header simile; il body di esempio segue.

```json
[
  {
    "user_id": 101,
    "mail": "firmatario1@example.com",
    "name": "Mario",
    "surname": "Rossi",
    "phone": "+393331234567",
    "cf": null,
    "controparte_ids": [
      1001,
      1002,
      1003
    ],
    "metadata": "{}"
  },
  {
    "user_id": 102,
    "mail": "firmatario2@example.com",
    "name": "Luigi",
    "surname": "Bianchi",
    "phone": "+393337654321",
    "cf": "RSSMRA80A01H501Z",
    "controparte_ids": [
      1001,
      1002
    ],
    "metadata": "{\n  \"date_of_birth\": \"\",\n  \"place_of_birth\": \"\",\n  \"residence_city\": \"\",\n  \"residence_address\": \"\"\n}"
  },
  {
    "user_id": 103,
    "mail": "firmatario3@example.com",
    "name": "Anna",
    "surname": "Verdi",
    "phone": "",
    "cf": null,
    "controparte_ids": [
      1003
    ],
    "metadata": "{\n  \"date_of_birth\": \"\",\n  \"place_of_birth\": \"\",\n  \"residence_city\": \"\",\n  \"residence_address\": \"\"\n}"
  }
]
```
