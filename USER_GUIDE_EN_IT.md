# VanishCam — User Guide / Guida utente

Guide for the Windows EXE editions / Guida alle edizioni EXE per Windows.

**English:** read the first section. **Italiano:** vai alla seconda sezione.

---

## English

### 1. What VanishCam does

VanishCam adds disappearance effects to your webcam video. Choose an effect,
capture the empty background, then perform the matching hand gesture. You can
watch the result in the preview or use it in video calls and streams through
a virtual camera.

### 2. What you need

- A 64-bit Windows PC, a working webcam and an active Internet connection.
- An active license for the email address supplied with your purchase.
- Speakers or headphones for the Naruto and Goku sound effects.
- Optional: OBS Studio with its OBS Virtual Camera driver for video calls.

You do not need to install Python. If the download is a ZIP archive, extract
it before opening the EXE. Keep your camera still and use even lighting so
your face and hands are clearly visible.

### 3. Activate your license

1. Open the EXE you received. Allow a few moments for startup.
2. On first launch, enter the email associated with your license.
3. Click **Attiva e avvia** (Activate and start).
4. Once the license is accepted, continue to the effect/camera selection.

**Only your email is required.** There is no password, registration form or
email confirmation. If your email has not yet been activated, contact the
seller or support team that provided your license.

The app remembers your email in your Windows profile. On later launches it
still checks the license online before starting, then checks it periodically
while you use the app. There is no offline activation mode.

Your license is associated with one PC. **Only one VanishCam instance may be
open at a time, across all editions.** Close one edition before opening another.
To move your license to a different PC, contact support for a device reset.
Copying the EXE does not transfer the license. Do not delete the local license
data or reinstall Windows as a way to fix an activation error: a device reset
may then be needed.

After a crash or forced shutdown, wait up to **two minutes** before trying
again. If the license is disabled or Internet access is lost for too long,
the app stops and releases the cameras. Reconnect or contact support, then
reopen the app.

### 4. Choose your effect

| EXE | Available effects |
| --- | --- |
| `VanishCam.exe` | Normal Vanish (`1`), Naruto Vanish (`2`), Particles (`3`), Goku (`4`), Itachi (`5`) |
| `Naruto Vanish Effect.exe` | Naruto, selected automatically |
| `Goku Vanish Effect.exe` | Goku, selected automatically |
| `Normal and Particles Vanish.exe` | Normal Vanish (`1`) or Particles (`2`) |

Where a menu is shown, click an effect or press its number.

### 5. Select the webcam and capture the background

1. In the webcam selection screen, check the live preview.
2. Use the `-` / `+` buttons, keys `0`–`9`, or `A` / `D` to change cameras.
3. Click **USA QUESTA WEBCAM** (Use this webcam) or press `Enter` to confirm.
   Press `R` to retry the selected camera, or `Esc` to cancel.
4. **Step completely out of the camera frame for four seconds.** The app
   captures the empty room. Keep your hands out of view too.
5. Wait for the console message saying the background is ready, then step
   back into the frame. You can now perform the gesture for your effect.

Capture the background again with `Space` whenever you move the webcam or
change the scene. People or objects moving behind you can affect the result.
You can minimize the console window; closing it may also close the app.

### 6. Activate an effect and reappear

| Effect | How to activate it | How to reappear |
| --- | --- | --- |
| **Normal Vanish** | Raise your index and middle fingers in a V sign. Your silhouette dissolves over about 3.6 seconds. | Press `R`. |
| **Particles** | Make the same V sign. Your silhouette breaks into drifting fragments over about 2.1 seconds. | Press `R`. |
| **Naruto Vanish** | Bring both palms together, with fingers side by side, not interlaced. Keep both hands visible. Smoke and a falling wooden log replace you. | Press `R`. |
| **Goku** | Hold your straight, joined index and middle fingers against your forehead for one second. Comic-style streaks accompany the teleport. | Lower your hand, then repeat the gesture for one second. |
| **Itachi Uchiha Disappear** | Touch both hands together in front of the center of your chest. Your silhouette turns into flapping crows over about 4 seconds; a translucent blood-red texture covers the room and Sharingan eyes briefly appear at the top. The red background remains while you are invisible. | Release your hands, return to the frame, then touch them at your chest again. The crows rebuild your silhouette and the room returns to normal. |

For Goku, release the pose before using it again. If the pose is interrupted,
you may need to start the hold again. The console shows the countdown. Sound
plays on both disappearance and reappearance; Naruto plays sound when you
disappear. Normal Vanish and Particles do not add a sound effect.

### 7. Keyboard controls

Click the preview window first so it receives your keyboard input.

| Key | Action |
| --- | --- |
| `Space` | Capture a new background. Step out of view for four seconds again. |
| `R` | Reappear in Normal, Naruto or Particles; start the animated return in Itachi after you return to frame. Disabled in Goku mode. |
| `V` | Manually start Normal, Naruto, Particles or Itachi. Disabled in Goku mode. |
| `F` | Toggle fullscreen. |
| `Q` or `Esc` | Exit the app and release the cameras and license session. |

To change effects after starting the webcam, exit and reopen the app.

### 8. Use the effect in a video call

1. Install OBS Studio with the OBS Virtual Camera driver.
2. If OBS is open, make sure its **Start Virtual Camera** output is stopped.
3. Open VanishCam, activate your license, select the webcam and capture the
   background. VanishCam automatically tries to open OBS Virtual Camera.
4. Check the console for confirmation that virtual output is active.
5. In your video-call or streaming app, choose **OBS Virtual Camera** as
   the camera instead of your physical webcam. Keep VanishCam running.

The preview and virtual output show the same video. The virtual camera carries
video, not the sound effects. Sounds play through your computer's audio output;
to send them to a call or stream, configure that app to capture computer audio.

If you instead want to compose a scene inside OBS, launch VanishCam without
direct virtual output. Open PowerShell in the EXE folder and run, for example:

```powershell
& ".\VanishCam.exe" --no-virtual-camera
```

In OBS add a **Window Capture** source for **Webcam - Anteprima**, then start
the virtual camera from OBS. Choose either direct output from VanishCam or
output from OBS; both cannot produce OBS Virtual Camera at the same time.

### 9. Troubleshooting

| Problem | What to do |
| --- | --- |
| License not active | Check the spelling of your license email and ask the seller/support team to verify activation. |
| License associated with another PC | Ask support to transfer/reset the device association. |
| Another edition is already open | Close it before starting this one. After a crash, wait up to two minutes. |
| License check or connection error | Check Internet access, wait a moment and reopen the app. Internet is required during use. |
| Webcam unavailable | Close other apps using the physical webcam, check Windows camera permissions and try another camera in the selection screen. |
| Background looks wrong or you remain visible | Press `Space`, leave the frame completely for four seconds, then return. Keep the webcam still. |
| Gesture not recognized | Improve lighting, keep the hand fully in view and hold the correct pose clearly. For Goku, keep two joined fingers at your forehead for a full second. |
| Keyboard shortcuts do nothing | Click the preview window first. Remember that `R` and `V` are disabled in Goku. |
| Virtual camera unavailable | Check that the driver is installed and OBS is not already producing virtual output. You can use the local preview without a virtual camera. |
| No sound | Check the Windows volume mixer, selected output and speakers/headphones. Normal and Particles are silent. |
| Video is slow | Close demanding apps. For a lower workload, run the command below from PowerShell in the EXE folder. |

```powershell
& ".\VanishCam.exe" --width 640 --height 360 --fps 24
```

Replace `VanishCam.exe` with the filename of your edition when needed. If a
problem persists, send support the EXE name, your Windows version and the
error text shown in the console. Never send local license credential files.

### 10. Privacy

Webcam frames are processed on your PC. VanishCam does not record or upload
your webcam feed. Empty-background images are used in memory for the effect.
License checks send your license email, an anonymous installation identifier,
a hashed device identifier and session information to Firebase. No password
is collected. Video-call or streaming software you use has its own data practices.

---

## Italiano

### 1. Cosa fa VanishCam

VanishCam aggiunge effetti di sparizione al video della webcam. Scegli un
effetto, acquisisci lo sfondo vuoto ed esegui il gesto corrispondente con le
mani. Puoi vedere il risultato nell'anteprima oppure usarlo in videochiamate
e dirette tramite una webcam virtuale.

### 2. Cosa serve

- Un PC Windows a 64 bit, una webcam funzionante e una connessione Internet attiva.
- Una licenza attiva per l'email comunicata con l'acquisto.
- Altoparlanti o cuffie per gli effetti sonori di Naruto e Goku.
- Facoltativo: OBS Studio con il driver OBS Virtual Camera per le videochiamate.

Non devi installare Python. Se ricevi un archivio ZIP, estrailo prima di aprire
l'EXE. Tieni ferma la webcam e usa una luce uniforme, in modo che volto e mani
siano ben visibili.

### 3. Attiva la licenza

1. Apri l'EXE ricevuto e attendi qualche istante per l'avvio.
2. Al primo avvio inserisci l'email associata alla tua licenza.
3. Premi **Attiva e avvia**.
4. Dopo la verifica, prosegui con la scelta dell'effetto e della webcam.

**Serve soltanto l'email.** Non vengono richieste password, registrazione o
conferme via email. Se l'indirizzo non è ancora attivo, contatta il venditore
o l'assistenza che ti ha fornito la licenza.

L'app ricorda l'email nel profilo Windows. Anche agli avvii successivi verifica
la licenza online prima di partire e ripete il controllo durante l'utilizzo.
Non è prevista un'attivazione offline.

La licenza è associata a un solo PC. **Può essere aperta una sola istanza di
VanishCam alla volta, considerando tutte le edizioni.** Chiudi un'edizione prima
di aprirne un'altra. Per spostare la licenza su un altro PC, chiedi il ripristino
del dispositivo all'assistenza. Copiare l'EXE non trasferisce la licenza. Non
cancellare i dati locali della licenza e non reinstallare Windows per risolvere
un errore di attivazione: potrebbe poi essere necessario un ripristino.

Dopo un arresto anomalo o una chiusura forzata, attendi fino a **due minuti**
prima di riprovare. Se la licenza viene disattivata o Internet manca troppo
a lungo, l'app si ferma e libera le webcam. Riconnettiti o contatta l'assistenza,
poi riapri l'app.

### 4. Scegli l'effetto

| EXE | Effetti disponibili |
| --- | --- |
| `VanishCam.exe` | Normal Vanish (`1`), Naruto Vanish (`2`), Particles (`3`), Goku (`4`), Itachi (`5`) |
| `Naruto Vanish Effect.exe` | Naruto, selezionato automaticamente |
| `Goku Vanish Effect.exe` | Goku, selezionato automaticamente |
| `Normal and Particles Vanish.exe` | Normal Vanish (`1`) oppure Particles (`2`) |

Quando compare il menu, clicca sull'effetto oppure premi il numero corrispondente.

### 5. Scegli la webcam e acquisisci lo sfondo

1. Nella schermata di selezione della webcam, controlla l'anteprima dal vivo.
2. Usa i pulsanti `-` / `+`, i tasti `0`–`9` oppure `A` / `D` per cambiare webcam.
3. Clicca **USA QUESTA WEBCAM** o premi `Invio` per confermare. Premi `R` per
   riprovare la webcam selezionata oppure `Esc` per annullare.
4. **Esci completamente dall'inquadratura per quattro secondi.** L'app acquisisce
   la stanza vuota: anche le mani devono essere fuori dall'immagine.
5. Aspetta il messaggio nella console che conferma che lo sfondo è pronto,
   poi rientra nell'inquadratura. Ora puoi eseguire il gesto dell'effetto scelto.

Acquisisci nuovamente lo sfondo con `Spazio` quando sposti la webcam o cambi
la scena. Persone o oggetti che si muovono dietro di te possono influire sul
risultato. Puoi minimizzare la console; chiuderla può terminare anche l'app.

### 6. Attiva un effetto e riappari

| Effetto | Come attivarlo | Come riapparire |
| --- | --- | --- |
| **Normal Vanish** | Alza indice e medio formando una V. La sagoma si dissolve in circa 3,6 secondi. | Premi `R`. |
| **Particles** | Fai lo stesso segno a V. La sagoma si disperde in frammenti trasportati dal vento in circa 2,1 secondi. | Premi `R`. |
| **Naruto Vanish** | Unisci entrambi i palmi con le dita affiancate, senza intrecciarle. Tieni visibili entrambe le mani. Al tuo posto compaiono fumo e un tronco che cade. | Premi `R`. |
| **Goku** | Tieni indice e medio distesi, uniti e appoggiati alla fronte per un secondo. Delle scie in stile fumetto accompagnano il teletrasporto. | Abbassa la mano, poi ripeti il gesto per un secondo. |
| **Itachi Uchiha Disappear** | Fai toccare entrambe le mani davanti al centro del petto. La sagoma si trasforma in corvi in circa 4 secondi; una texture rosso sangue semitrasparente copre la stanza e gli occhi Sharingan appaiono brevemente in alto. Il rosso rimane mentre sei invisibile. | Separa le mani, rientra nell'inquadratura e ripeti il gesto al petto. I corvi ricompongono la sagoma e la stanza torna normale. |

In Goku devi rilasciare la posa prima di ripeterla. Se interrompi il gesto,
potresti dover ricominciare il tempo di tenuta. La console mostra il conto
alla rovescia. Il suono parte sia quando sparisci sia quando riappari; Naruto
riproduce il suono quando sparisci. Normal Vanish e Particles non aggiungono
effetti sonori.

### 7. Comandi da tastiera

Clicca prima sulla finestra di anteprima, così riceverà i comandi della tastiera.

| Tasto | Azione |
| --- | --- |
| `Spazio` | Acquisisce un nuovo sfondo. Esci di nuovo dall'inquadratura per quattro secondi. |
| `R` | Ti fa riapparire in Normal, Naruto o Particles; in Itachi avvia il ritorno animato quando sei di nuovo nell'inquadratura. Disattivato in Goku. |
| `V` | Avvia manualmente Normal, Naruto, Particles o Itachi. Disattivato in Goku. |
| `F` | Attiva o disattiva lo schermo intero. |
| `Q` oppure `Esc` | Chiude l'app e libera webcam e sessione della licenza. |

Per cambiare effetto dopo l'avvio della webcam, esci e riapri l'app.

### 8. Usa l'effetto in videochiamata

1. Installa OBS Studio con il driver OBS Virtual Camera.
2. Se OBS è aperto, verifica che la sua funzione **Avvia fotocamera virtuale**
   sia ferma.
3. Apri VanishCam, attiva la licenza, scegli la webcam e acquisisci lo sfondo.
   VanishCam prova ad aprire automaticamente OBS Virtual Camera.
4. Controlla nella console il messaggio che conferma l'uscita virtuale attiva.
5. Nell'app di videochiamata o streaming scegli **OBS Virtual Camera** come
   videocamera, al posto della webcam fisica. Lascia VanishCam in esecuzione.

L'anteprima e l'uscita virtuale mostrano lo stesso video. La webcam virtuale
trasmette il video, non gli effetti sonori. I suoni escono dagli altoparlanti
o dalle cuffie del PC: per inviarli in una chiamata o diretta, configura anche
l'acquisizione dell'audio del computer nell'app che utilizzi.

Se invece vuoi comporre una scena dentro OBS, avvia VanishCam senza l'uscita
virtuale diretta. Apri PowerShell nella cartella dell'EXE ed esegui, per esempio:

```powershell
& ".\VanishCam.exe" --no-virtual-camera
```

In OBS aggiungi una sorgente **Cattura finestra** per **Webcam - Anteprima**,
poi avvia la fotocamera virtuale da OBS. Scegli se far produrre l'uscita a
VanishCam oppure a OBS: non possono usare contemporaneamente la stessa
OBS Virtual Camera come uscita.

### 9. Risoluzione dei problemi

| Problema | Cosa fare |
| --- | --- |
| Licenza non attiva | Controlla l'email inserita e chiedi al venditore o all'assistenza di verificare l'attivazione. |
| Licenza associata a un altro PC | Chiedi all'assistenza il trasferimento o il ripristino del dispositivo. |
| Un'altra edizione è già aperta | Chiudila prima di avviare questa. Dopo un arresto anomalo attendi fino a due minuti. |
| Errore di connessione o verifica licenza | Controlla Internet, attendi un momento e riapri l'app. La connessione serve anche durante l'uso. |
| Webcam non disponibile | Chiudi le altre app che usano la webcam fisica, controlla i permessi della fotocamera in Windows e prova un'altra webcam nella schermata di selezione. |
| Sfondo sbagliato o sagoma ancora visibile | Premi `Spazio`, esci completamente dall'inquadratura per quattro secondi, poi rientra. Non spostare la webcam. |
| Gesto non riconosciuto | Migliora la luce, tieni la mano interamente visibile ed esegui bene la posa. In Goku tieni due dita unite alla fronte per un secondo intero. |
| I tasti non funzionano | Clicca prima sull'anteprima. Ricorda che `R` e `V` sono disattivati in Goku. |
| Webcam virtuale non disponibile | Verifica che il driver sia installato e che OBS non stia già producendo l'uscita virtuale. Puoi usare l'anteprima locale anche senza webcam virtuale. |
| Audio assente | Controlla mixer volume di Windows, uscita selezionata e cuffie o altoparlanti. Normal e Particles sono silenziosi. |
| Video a scatti | Chiudi le app più pesanti. Per ridurre il carico, esegui il comando seguente da PowerShell nella cartella dell'EXE. |

```powershell
& ".\VanishCam.exe" --width 640 --height 360 --fps 24
```

Sostituisci `VanishCam.exe` con il nome della tua edizione quando necessario.
Se il problema continua, comunica all'assistenza il nome dell'EXE, la versione
di Windows e il testo dell'errore nella console. Non inviare i file locali
contenenti le credenziali della licenza.

### 10. Privacy

I fotogrammi della webcam vengono elaborati sul PC. VanishCam non registra e
non carica online il flusso della webcam. Lo sfondo vuoto viene usato in memoria
per creare l'effetto. I controlli della licenza inviano a Firebase l'email,
un identificatore anonimo dell'installazione, un identificatore del dispositivo
in forma di hash e le informazioni di sessione. Non viene raccolta una password.
Le app di videochiamata o streaming che utilizzi seguono le proprie informative.
