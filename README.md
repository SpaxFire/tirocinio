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
