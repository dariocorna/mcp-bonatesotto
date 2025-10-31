# Istruzioni MCP Server (Facebook, Google Drive, Docs Locali)

Benvenuto nel server MCP personale dedicato all'integrazione con Facebook, Google Drive e alla consultazione di documentazione locale.  
Queste istruzioni vengono distribuite insieme al codice sorgente e descrivono il comportamento base del server.  
Puoi aggiungere note operative locali tramite l'interfaccia disponibile su `/ui/instructions`.

## Funzionalità principali

1. **Facebook Graph API**
   - `POST /facebook/profile` per leggere informazioni di profilo/pagina.
   - `POST /facebook/feed` per ottenere un feed con filtri facoltativi (limite, intervalli temporali, cursori).
   - `POST /facebook/posts` per creare un nuovo post (supporto a publish immediato o pianificato).
   - Richiede un token valido (`FACEBOOK_ACCESS_TOKEN`) definito in `.env`.

2. **Google Drive**
   - `POST /google-drive/files` per elencare file visibili con il service account.
   - `POST /google-drive/files/download` per scaricare contenuti (risposta base64).
   - `POST /google-drive/files/upload` per caricare file nelle cartelle condivise o Shared Drive accessibili.
   - Configurare `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` e altri parametri nel file `.env`.

3. **Documentazione locale**
   - Configura `DOCS_ROOT` nel file `.env` (default consigliato: `~/devel/docs-dario`).
   - `GET /local-docs/tree?path=...` elenca sottocartelle e file testuali.
   - `GET /local-docs/file?path=sub/path.md` restituisce il contenuto UTF-8 (limite 5 MiB).
   - I percorsi sono validati per evitare traversal fuori da `DOCS_ROOT`.
   - Prima della prima esecuzione l’operatore deve leggere `@bonate init` per consultare `guidelines/index.md` e completare l’inizializzazione locale.

## Convenzioni di configurazione

- Mantieni `.mcp_cache/` presente e scrivibile: il server lo usa per memorizzare cache, indici e note locali.
- Le variabili presenti in `config.example.env` rappresentano il minimo necessario per produzione.
- Assicurati che `DOCS_ROOT` punti a una cartella esistente e leggibile dal server prima di usare `/local-docs/*`.
- Hydra/daemon script: eseguire `./mcp-daemon.sh start` per avviare il server in background (richiede virtualenv).

## Controllo stato e supporto

- `GET /health` risponde con `{ "status": "ok" }` per verificare rapidamente la disponibilità.
- `GET /` restituisce una risposta testuale minima per confermare il funzionamento.
- Log principali su `server.log` quando il daemon viene avviato tramite script.

## Aggiornamento di queste istruzioni

- Modifica direttamente questo file (`static/instructions_static.md`) per aggiornare la documentazione distribuita.
- Aggiungi istruzioni temporanee o locali tramite `/ui/instructions`: saranno salvate in `.mcp_cache/instructions.json`.
- I client MCP possono leggere entrambe le parti richiamando `GET /api/instructions`.

---

_Ultimo aggiornamento: 2025-03-??_  
Sostituisci questa nota quando adegui il server o le integrazioni.
