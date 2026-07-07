## Luca Artusio MAT. 343864

# Social Network Web App - Progetto di Tesi 🎓

## 📖 Descrizione
Questo repository contiene il codice sorgente di un'applicazione web completa di tipo social network, realizzata come progetto per la Tesi di Laurea Triennale in Informatica all'Università degli Studi di Ferrara. 

L'obiettivo principale del progetto è fornire una piattaforma interattiva che consenta agli utenti di interagire attraverso la pubblicazione di contenuti testuali e multimediali, la gestione di relazioni sociali (come i meccanismi di "follow" e "mi piace") e l'organizzazione delle informazioni in categorie. Il sistema si distingue per l'impiego di un database a grafo, ideale per modellare e interrogare le complesse dinamiche relazionali tipiche dei social network, e per l'utilizzo di un approccio server-rendered moderno ed efficiente.

## 🛠️ Tecnologie Utilizzate

Il progetto è stato sviluppato adottando tecnologie moderne e complementari per garantire elevate prestazioni e un'ottima User Experience:

* **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python) - Framework performante scelto per la tipizzazione forte, la gestione rapida delle richieste HTTP e la facile strutturazione in router e servizi.
* **Database:** [Neo4j](https://neo4j.com/) - Database a grafo utilizzato per gestire in modo naturale ed efficiente entità e relazioni complesse (es. *Utente segue Utente*, *Utente mette like a Post*) tramite query Cypher.
* **Frontend:** [HTMX](https://htmx.org/) e [Tailwind CSS](https://tailwindcss.com/) con template HTML (Jinja2) - HTMX abilita interazioni dinamiche e aggiornamenti parziali del DOM tramite semplici attributi HTML (es. infinite scroll, active search), mentre Tailwind CSS garantisce una stilizzazione modulare, reattiva e coerente con un approccio utility-first.

## ⚙️ Architettura

L'applicazione è strutturata secondo un solido **Modello a Tre Strati (Three-Tier Architecture)**:
1. **Presentation Layer (Frontend):** Gestisce l'interfaccia utente in modo dichiarativo e dinamico, minimizzando l'uso di JavaScript custom.
2. **Application Layer (Business Logic):** API modulari in FastAPI che elaborano le richieste, gestiscono l'autenticazione, la validazione dei file media e orchestrano l'interazione con il database.
3. **Data Layer:** Persistenza dei dati affidata a Neo4j, che ottimizza le query trasversali sulle reti sociali rispetto ai classici database relazionali.

## ✨ Funzionalità Implementate

* 🔐 **Registrazione e Autenticazione:** Sistema di Login/Registrazione sicuro basato su token JWT gestiti lato server tramite cookie `HttpOnly`.
* 📝 **Operazioni CRUD sui Post:** Possibilità di creare, leggere, aggiornare ed eliminare post, con supporto al caricamento di file multimediali (immagini fino a 5MB) e classificazione tramite categorie.
* 💬 **Sistema di Commenti:** Interazioni dirette sotto i post tramite operazioni CRUD dedicate ai commenti.
* ❤️ **Interazioni Sociali (Like e Follow):** Sistemi nativi per mettere "Mi piace" ai contenuti e seguire altri profili per aggiornare dinamicamente il proprio feed.
* 🧭 **Pagina Scopri e Infinite Scroll:** Sezione dedicata all'esplorazione dei contenuti con caricamento continuo e dinamico (Infinite Scroll) implementato tramite HTMX per una navigazione fluida.
* 🔍 **Sistema di Ricerca (Active Search):** Motore di ricerca reattivo integrato con HTMX per trovare post, utenti e commenti con aggiornamento istantaneo dei risultati.
* ⚙️ **Impostazioni Account e Modali:** Realizzazione di operazioni CRUD degli account (l'eliminazione consiste nella disattivazione dell'account, senza rimozione dal database) e gestione fluida delle informazioni personali (profilo, email, password) modificabili tramite finestre modali dinamiche che non interrompono l'esperienza di navigazione.
* 🛡️ **Gestione Ruoli e Permessi:** Distinzione chiara tra ruoli `Utente` e `Amministratore`, con controlli di autorizzazione per proteggere le rotte e permettere azioni privilegiate agli admin (es. gestione degli account altrui).

## ▶️ Setup e avvio su qualsiasi PC

Questa sezione descrive i passaggi minimi per installare e avviare il progetto da zero.

Ambiente di riferimento: Linux.

### Prerequisiti

1. Python 3.10+ installato
2. Node.js 24+ e npm 10+ installati
3. Git installato

### 1) Clona il repository

	git clone https://github.com/SpaxFire/tirocinio
	cd tirocinio
    git checkout Progetto_Sistemi
    git pull origin Progetto_Sistemi

### 2) Installa Node.js 24 (consigliato con nvm)

	curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
	export NVM_DIR="$HOME/.nvm"
	[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
	nvm install 24
	nvm use 24
	node -v
	npm -v

### 3) Crea e attiva l'ambiente virtuale Python

	python3 -m venv .venv
	source .venv/bin/activate

### 4) Installa le dipendenze Python

	pip install -r requirements.txt

### 5) Installa le dipendenze frontend

	npm install

### 6) Avvia il backend FastAPI (terminale 1)

	source .venv/bin/activate
	export NEO4J_URI=bolt://127.0.0.1:7687
	export NEO4J_USER=neo4j
	export NEO4J_PASSWORD=neo4jpassword
	fastapi dev app/main.py

### 7) Avvia Tailwind in watch (terminale 2)

	npm run tw:watch

Se usi `nvm`, puoi allineare automaticamente la versione Node richiesta:

	nvm use

### 8) Apri l'app nel browser

	http://127.0.0.1:8000

### Nota importante

Ogni nuovo terminale richiede la riattivazione dell'ambiente virtuale prima dei comandi Python:

	source .venv/bin/activate

## Audit separato (Server + Validator)

Da questa versione (separata da progetto originale di Luca) puoi eseguire la validazione audit come servizio separato.

L'avvio precedente con solo server web continua a funzionare: se `AUDIT_VALIDATOR_URL` non e impostata, il server usa automaticamente la coda locale come fallback.

### Avvio in locale con 2 processi

Terminale A (validator):

	. .venv/bin/activate
	export AUDIT_TX_SIGNING_SECRET=tx-secret-dev
	export AUDIT_BLOCK_SIGNING_SECRET=block-secret-dev
	python -m uvicorn app.validator_main:validator_app --host 127.0.0.1 --port 8001 --reload

Terminale B (server web):

	. .venv/bin/activate
	# Se usi Neo4j locale:
	export NEO4J_URI=bolt://127.0.0.1:7687
	export NEO4J_USER=neo4j
	export NEO4J_PASSWORD=neo4jpassword
	# Se usi Neo4j online (Aura), sostituisci i valori sopra con quelli remoti.
	# Esempio: export NEO4J_URI=neo4j+s://<instance-id>.databases.neo4j.io
	export AUDIT_VALIDATOR_URL=http://127.0.0.1:8001
	export AUDIT_TX_SIGNING_SECRET=tx-secret-dev
	export AUDIT_BLOCK_SIGNING_SECRET=block-secret-dev
	python -m fastapi dev app/main.py

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

## Containerizzazione con Docker e Docker Compose

Il progetto include ora una configurazione completa per avviare i servizi principali in container:

* backend FastAPI (`backend`)
* database Neo4j locale opzionale (`neo4j`, profilo `local-db`)
* broker MQTT Mosquitto (`mqtt-broker`)
* servizio validator audit (`audit-validator`)

### Prerequisiti

1. Docker Engine installato
2. Docker Compose plugin (`docker compose`) installato

### File aggiunti

* `Dockerfile`: immagine applicativa Python per backend/validator
* `docker-compose.yml`: orchestrazione multi-servizio
* `.env.docker.example`: variabili ambiente di riferimento per Compose
* `infra/mosquitto/mosquitto.conf`: configurazione broker MQTT

### Avvio rapido

1) Copia il file di ambiente Docker:

	cp .env.docker.example .env.docker

2) Avvia tutti i servizi:

	docker compose up -d --build

	# Opzionale: se vuoi anche Neo4j locale nel compose
	docker compose --profile local-db up -d

3) Verifica lo stato:

	docker compose ps

4) Apri i servizi:

* App web: `http://127.0.0.1:8000`
* Validator audit: `http://127.0.0.1:8001/internal/audit/health`

Se vuoi avviare anche Neo4j locale (in alternativa a un Neo4j remoto), usa:

	docker compose --profile local-db up -d

In quel caso, Neo4j Browser sarà disponibile su `http://127.0.0.1:7474`.

### Stop e cleanup

Stop:

	docker compose down

Stop + rimozione volumi (attenzione: cancella i dati persistiti nei volumi Docker):

	docker compose down -v

### Note architetturali

* Il backend usa `AUDIT_VALIDATOR_URL=http://audit-validator:8001` sulla rete Docker interna.
* Neo4j e configurato via env (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`) e ora non dipende piu da credenziali hardcoded.
* I file di audit e upload restano persistenti tramite bind mount sulle cartelle locali `data/` e `static/uploads/`.

### Endpoint del validatore

* `GET /internal/audit/health`: healthcheck del servizio validatore.
* `POST /internal/audit/transactions`: riceve una transazione firmata, verifica la firma e crea/accoda un blocco.
* `GET /internal/audit/chain`: restituisce la catena (anche filtrata con `user`, `event_type`, `start_time`, `end_time`) e il campo `is_valid`.

### Verifica lato admin

La pagina admin `/admin/audit` prova a leggere la catena dal validatore remoto quando configurato; in caso di fallback usa la vista locale. In entrambi i casi viene mostrato lo stato di validita (`is_valid`) della chain.
