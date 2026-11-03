# Gestione licenze VanishCam

Progetto Firebase: **vanishcam-licenses-20261027** (VanishCam Licenses).

[Apri Firestore](https://console.firebase.google.com/project/vanishcam-licenses-20261027/firestore/databases/-default-/data).
Il database e' `(default)`, posizione `nam5`. Non sono necessarie Cloud Functions,
un server privato o credenziali amministrative dentro gli EXE. Il progetto usa
il piano gratuito; restano applicabili le quote Firebase. Il codice non collega
un account di fatturazione e non abilita l'upgrade a Identity Platform.

## Attivare una licenza

1. Apri Firestore Database > Dati.
2. Crea la raccolta `licenses`, se non esiste.
3. Crea un documento con ID uguale all'email del cliente, tutta in minuscolo,
   senza spazi. Esempio: `cliente@example.com`.
4. Aggiungi `email` di tipo **string**, con lo stesso indirizzo.
5. Aggiungi `active` di tipo **boolean**, valore **true**. Non usare la stringa
   `"true"`: deve essere il valore booleano.
6. Salva. L'utente puo' aprire una qualsiasi delle edizioni e inserire l'email.

Non devi creare un utente email/password in Firebase Authentication. L'app
genera automaticamente un'identita' anonima per il dispositivo. Non esiste
un'iscrizione, una password o una mail di conferma nell'esperienza del cliente.

## Disattivare e riattivare

Nel documento `licenses/EMAIL` cambia `active` in **false**. Un nuovo avvio viene
subito rifiutato. L'app gia' aperta si ferma al successivo controllo, normalmente
entro circa 25 secondi piu' il tempo di rete. Per riattivare, rimetti **true**.
Dopo una revoca/chiusura senza rilascio puo' essere necessario attendere la
scadenza della vecchia sessione, al massimo due minuti dall'ultimo rinnovo.

## Cambiare PC o ripristinare un profilo Windows reinstallato

1. Imposta `licenses/EMAIL.active = false`.
2. Fai chiudere l'app e attendi due minuti, cosi' non resta una sessione valida.
3. Elimina SOLO il documento `licenseBindings/EMAIL` dalla console Firestore.
   Non eliminare la licenza e non cancellare sessioni ancora attive per forzare
   uno sblocco: la scadenza protegge dal doppio utilizzo durante il trasferimento.
4. Riporta `licenses/EMAIL.active = true`.
5. Il cliente inserisce la stessa email sul nuovo PC. La prima attivazione
   riuscita crea la nuova associazione. Il vecchio dispositivo viene rifiutato.

Il ripristino serve anche dopo la rimozione dei dati locali protetti o la
reinstallazione di Windows: l'identita' anonima precedente non e' recuperabile
dal solo indirizzo email. Non eliminare gli utenti anonimi in Authentication
se vuoi conservare le associazioni esistenti.

## Dati creati automaticamente

| Raccolta | Contenuto | Gestione |
| --- | --- | --- |
| `licenses/EMAIL` | Email e `active` | Li gestisci tu nella console |
| `licenseBindings/EMAIL` | UID anonimo, hash del dispositivo, data di associazione | App; elimina il documento solo per un trasferimento autorizzato |
| `licenseSessions/EMAIL` | UID, hash dispositivo, ID sessione, modalita', `lastSeenAt`, `released` | App; normalmente non modificarlo |

La modalita' e' informativa: questa implementazione usa una licenza comune per
tutte le edizioni, non un acquisto separato per ciascun effetto. E' consentita
una sola istanza attiva complessiva, anche se due EXE sono sullo stesso PC.
Gli effetti aggiunti prima dell'aggiornamento delle regole, come Itachi, sono
registrati temporaneamente come `full`: la licenza rimane attiva senza ampliare
i permessi del dispositivo o della sessione.

## Come viene mantenuto il limite

- Il PC riceve un'identita' anonima Firebase, senza credenziali da inserire.
- Il token di rinnovo e l'email sono salvati con Windows DPAPI nel profilo
  corrente, sotto `%LOCALAPPDATA%\VanishCam\licensing\PROJECT_ID\identity.bin`.
- Il dispositivo e' identificato con un hash del MachineGuid di Windows.
  Il GUID originale non viene inviato a Firebase. Le credenziali DPAPI copiate
  su un altro PC/profilo Windows non si decifrano normalmente.
- L'acquisizione usa una scrittura atomica Firestore con precondizioni di
  versione. Le regole server verificano `active`, l'associazione e l'esclusivita'
  della sessione: non basta modificare un valore locale.
- Ogni 25 secondi l'app rinnova la sessione usando il timestamp del server.
  La sessione scade dopo 120 secondi senza rinnovi. Alla chiusura normale viene
  rilasciata immediatamente; dopo un crash scade automaticamente.
- Se la rete manca, l'app non prolunga da sola la validita': interrompe l'uscita
  prima della scadenza server (margine di 15 secondi). A ogni avvio serve sempre
  una verifica online riuscita, anche se l'email e' gia' memorizzata.
- I controlli continuano nei menu, nell'anteprima e prima dell'invio di ogni
  fotogramma virtuale. Una revoca chiude anche webcam, uscita virtuale e audio.

La sola email non dimostra che chi la inserisce sia il proprietario della
casella. Come richiesto non vengono chieste password o conferme: chi conosce
un'email attiva puo' tentare la prima associazione finche' non e' gia' legata a
un PC. Dopo l'associazione servono anche l'identita' protetta del dispositivo
e una sessione valida. Per questo e' opportuno attivare l'email quando consegni
il prodotto al cliente. Come ogni licenza controllata da un programma locale,
questa e' una protezione commerciale di base, non un DRM inviolabile.

## Distribuzione e manutenzione

`license_config.json` contiene solo la configurazione pubblica Firebase e va
incluso in ogni build. `VanishCam.spec` lo include automaticamente in tutte le
edizioni. `license_client.py` viene incluso da PyInstaller tramite l'import.
Non distribuire credenziali di servizio, login del CLI, dati del tuo profilo
Windows o la cartella di sviluppo `licensing_backend/node_modules`.

Ricompila con `BUILD_WINDOWS.bat` e distribuisci gli EXE nuovi. Le copie vecchie
senza il controllo licenza non acquisiscono questa funzione retroattivamente.
`--self-test` controlla solo modelli e file, senza videocamera o effetti, e non
richiede una licenza. Gli EXE distribuiti non hanno una modalita' offline;
gli script Python avviati da `AVVIA_LOCALE.bat` sono la versione di sviluppo
locale e partono senza verifica Firebase.

Le regole private sono in `licensing_backend/firestore.rules`, escluso da Git.
Prima di eseguire i test o pubblicare modifiche, assicurati che il file sia
presente nella tua copia locale. Per pubblicare modifiche:

```powershell
cd licensing_backend
$env:DEBUG = ''
firebase deploy --only firestore:rules --project vanishcam-licenses-20261027
```

Test delle regole (Node 22+, Java e Firebase CLI):

```powershell
npm ci
$env:DEBUG = ''
firebase emulators:exec --only firestore --project demo-vanishcam-licenses "npm test"
```

I test usano un progetto demo emulato, non le licenze dei clienti. Le credenziali
Firebase amministrative non sono richieste dal client desktop.

## Privacy

L'informativa del prodotto deve descrivere l'invio a Firebase dell'email, di un
identificatore anonimo, dell'hash del dispositivo e dello stato della sessione,
compresi i timestamp e la modalita'. I servizi di rete possono trattare metadati
tecnici delle richieste. Questi controlli non inviano immagini o audio della
webcam. La descrizione precedente "tutto offline" non vale per le licenze.

Riferimenti: [identita' anonime](https://firebase.google.com/docs/auth/web/anonymous-auth),
[regole Firestore](https://firebase.google.com/docs/firestore/security/rules-conditions),
[API REST](https://firebase.google.com/docs/firestore/use-rest-api).
