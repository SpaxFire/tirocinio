# Social Network Web App

## 📖 Descrizione
Questo branch contiene il codice sorgente dell'espansione all'applicazione web di social network, realizzata da Luca Artusio (MAT. 343864) e Elia Lini (MAT. 344967) come progetto dell'insegnamento di Sistemi Distribuiti e Decentralizzati.

L'obiettivo principale del progetto è integrare i serivizi di audit-log, per la creazione di log immutabili e tracciabili tramite blockchain, e MQTT, per la gestione delle notifiche in tempo reale, il tutto containerizzato tramite docker.

## 🛠️ Tecnologie Utilizzate

### Backend
- **FastAPI** (Python) — API performanti, tipizzazione forte e documentazione automatica

### Database
- **Neo4j** — Database a grafo per relazioni complesse (follow, like, ecc.)

### Frontend
- **HTMX** + **Jinja2** — Interazioni dinamiche senza scrivere molto JavaScript
- **Tailwind CSS** — Styling moderno e responsive

### DevOps
- **Docker** + **Docker Compose**
- **Mosquitto** (MQTT broker)
- Audit trail con firma crittografica

## ⚙️ Architettura Aggiornata

L'applicazione segue un'architettura **Three-Tier** estesa con componenti distribuiti:

1. **Presentation Layer:** HTMX + templates Jinja2.
2. **Application Layer:** FastAPI con middleware per audit, validazione e publishing MQTT.
3. **Data Layer:** Neo4j per i dati relazionali.
4. **Real-time Layer:** MQTT Broker (Mosquitto) + client Paho per notifiche push e subscriber.
5. **Audit Layer:** Blockchain validator separato (servizio FastAPI) che registra transazioni in un file JSON chain immutabile.
6. **Notification Broker:** Fallback locale (in-memory + queue) per notifiche quando MQTT non è disponibile.

**Flusso tipico di un evento (es. nuovo post):**
- FastAPI valida e salva su Neo4j.
- Middleware genera evento audit → invia al Validator (blockchain).
- Pubblicazione su topic MQTT → notifiche real-time ai client connessi (via HTMX updates).
- Fallback su NotificationBroker locale.

## ✨ Funzionalità Implementate

- Registrazione e Login sicuri (JWT + HttpOnly cookies)
- CRUD Post con caricamento immagini (max 5MB)
- Sistema di Like e Follow
- Commenti annidati
- Feed dinamico con **Infinite Scroll**
- Ricerca attiva (active search)
- Pagine profilo e impostazioni account
- Ruoli Utente / Amministratore
- Sistema di **Audit Trail** con catena di blocchi firmati
- Containerizzazione completa

## ▶️ Setup e avvio su qualsiasi PC

Questa sezione descrive i passaggi minimi per installare e avviare il progetto da zero.

Ambiente di riferimento: Linux.

## 🚀 Avvio Rapido con Docker (Consigliato)

### Prerequisiti
- Docker Engine
- Docker Compose (plugin `docker compose`)

### 1. Clona il repository

    bash
    git clone https://github.com/SpaxFire/tirocinio.git
    cd tirocinio
    git checkout docker

### 2. Configura le variabili d'ambiente

    bash
    cp .env.docker.example .env.docker


### 3. Avvia i servizi

    bash
### Avvio standard (backend + validator + mosquitto)
    docker compose up -d --build

**N.B.** è necessario configurare correttamente le variabili per il servizio di neo4j nel file `.env.docker` (con quelle corrispondenti al server remoto).

### Avvio anche Neo4j locale (opzionale)
    docker compose --profile local-db up -d

**N.B.** è necessario che i parametri per il servizio di neo4j siano correttamente impostati nel file `.env.docker` (come nel file `.env.docker.example`).

### Avvio dei singoli servizi (opzionale)

    docker compose up -d --build --no-deps backend

### Stop e cleanup

Stop:

	docker compose down

Stop + rimozione volumi (attenzione: cancella i dati persistiti nei volumi Docker):

	docker compose down -v


### 4. Accedi all'applicazione

- **Web App**: http://localhost:8000
- **Neo4j Browser** (se avviato): http://localhost:7474 (user: `neo4j`, password: vedi `.env.docker`)
- **Validator Health**: http://localhost:8001/internal/audit/health

## Audit separato (Server + Validator) - Elia Lini (MAT. 344967)

Da questa versione (separata da progetto originale di Luca) puoi eseguire la validazione audit come servizio separato.

L'avvio precedente con solo server web continua a funzionare: se `AUDIT_VALIDATOR_URL` non e impostata, il server usa automaticamente la coda locale come fallback.

### Come funziona il validatore

Il validatore e un servizio FastAPI separato che riceve eventi di audit dal server principale e li trasforma in blocchi firmati della catena.

Flusso completo:

1. Il middleware del server intercetta ogni richiesta HTTP e costruisce un evento di audit (`event_type` + `payload`).
2. Se `AUDIT_VALIDATOR_URL` e valorizzata, il server crea una **transazione firmata** (HMAC-SHA256) e la invia al validatore su `POST /internal/audit/transactions`.
3. Il validatore verifica la firma della transazione, crea il blocco (con `previous_hash`, `hash`, `signature`) e lo salva in `data/audit_chain.json`.
4. Se il validatore non e configurato o non e raggiungibile, l'evento viene accodato su `data/pending_audit_events.json`.
5. Un task in background del server tenta periodicamente (ogni 30 secondi) il flush della coda pendente verso il validatore.

In questo modo non perdi eventi anche in caso di problemi temporanei di rete o se il validatore viene avviato dopo il server.

### Variabili ambiente utili

* `AUDIT_VALIDATOR_URL`: URL base del servizio validatore (es. `http://127.0.0.1:8001`). Se vuota, il server lavora in modalita coda locale persistente.
* `AUDIT_CHAIN_PATH`: percorso file catena audit (default: `data/audit_chain.json`).
* `AUDIT_PENDING_PATH`: percorso file coda eventi pendenti (default: `data/pending_audit_events.json`).
* `AUDIT_TX_SIGNING_SECRET`: segreto condiviso tra server e validatore per firmare/verificare le transazioni server -> validator.
* `AUDIT_BLOCK_SIGNING_SECRET`: segreto usato per firmare/verificare i blocchi della chain (separato da quello delle transazioni).

Compatibilita con versioni precedenti:

* `AUDIT_SIGNING_SECRET` resta supportata come fallback legacy (se valorizzata, viene usata per entrambi i flussi).

### Endpoint del validatore

* `GET /internal/audit/health`: healthcheck del servizio validatore.
* `POST /internal/audit/transactions`: riceve una transazione firmata, verifica la firma e crea/accoda un blocco.
* `GET /internal/audit/chain`: restituisce la catena (anche filtrata con `user`, `event_type`, `start_time`, `end_time`) e il campo `is_valid`.

### Verifica lato admin

La pagina admin `/admin/audit` prova a leggere la catena dal validatore remoto quando configurato; in caso di fallback usa la vista locale. In entrambi i casi viene mostrato lo stato di validita (`is_valid`) della chain.

## MQTT per notifiche real-time - Luca Artusio (MAT. 343864)

In questa espansione, MQTT è utilizzato per abilitare notifiche asincrone e real-time verso gli utenti connessi, riducendo il polling lato client e migliorando la reattività dell'interfaccia.

Il backend FastAPI pubblica eventi applicativi dopo le operazioni principali (es. like, commenti, nuovi post), usando Mosquitto come broker nella rete Docker (mqtt-broker); i client subscriber ricevono il messaggio e aggiornano la frontend tramite endpoint/partial HTMX.

### Come funziona (flusso di una notifica MQTT)
1. L’utente esegue un’azione tramite una rotta FastAPI.
2. La rotta è registrata nel router centrale `app/api/router.py` ed eseguita nel backend (`app/main.py` include `api_router`).
3. La logica dati aggiorna Neo4j tramite i moduli `app/db/*` (es. `app/db/post.py`, `app/db/comment.py`).
4. Dopo la persistenza, il modulo `mqtt_client` crea un evento notifica e lo pubblica sul broker MQTT.
5. Il modulo `mqtt_subscriber` riceve l’evento e lo invia al `notification_broker` locale, il quale lo distribuisce agli endpoint SSE/HTMX che aggiornano la UI.

Se MQTT non è disponibile, il modulo `mqtt_client` utilizza il fallback locale, contattando direttamente il `notification_broker` per non perdere l'evento.

### Variabili ambiente MQTT (riferimento operativo)

Nel branch Docker, la configurazione passa da `.env.docker` / `.env.docker.example` e `docker-compose.yml`.  
Le variabili chiave da documentare/usare sono:

* `MQTT_BROKER_HOST` (in Docker: `mqtt-broker`)
* `MQTT_BROKER_PORT` (tipicamente `1883`)
* `MQTT_USERNAME` e `MQTT_PASSWORD` (se autenticazione broker attiva)
* `MQTT_TOPIC` (default: `notifications.created`)

### Endpoint notifiche real-time

* `GET /notifications`: mostra la pagina con lo storico delle notifiche filtrato per tab e utente seguito, usando il contenuto salvato nel broker in memoria.
* `GET /notifications/stream`: apre uno stream SSE che invia al browser le nuove notifiche in tempo reale, aggiornando la UI senza ricaricare la pagina.

## Containerizzazione con Docker e Docker Compose

Il progetto include ora una configurazione completa per avviare i servizi principali in container:

* backend FastAPI (`backend`)
* database Neo4j locale opzionale (`neo4j`, profilo `local-db`)
* broker MQTT Mosquitto (`mqtt-broker`)
* servizio validator audit (`audit-validator`)

### File pertinenti

* `Dockerfile`: immagine applicativa Python per backend/validator
* `docker-compose.yml`: orchestrazione multi-servizio
* `.env.docker.example`: variabili ambiente di riferimento per Compose
* `infra/mosquitto/mosquitto.conf`: configurazione broker MQTT

### Note architetturali

* Il backend usa `AUDIT_VALIDATOR_URL=http://audit-validator:8001` sulla rete Docker interna.
* Neo4j e configurato via env (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`) e ora non dipende piu da credenziali hardcoded.
* I file di audit e upload restano persistenti tramite bind mount sulle cartelle locali `data/` e `static/uploads/`.
