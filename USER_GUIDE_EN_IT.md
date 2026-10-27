# VanishCam — User Guide / Guida utente

## English

### What you need

- A Windows PC and a working webcam.
- `VanishCam.exe`. Python is not required.
- Optional: OBS Studio with OBS Virtual Camera if you want to use the effect in video calls or streaming apps.

For the best result, keep the webcam still, use even lighting, and avoid people moving in the background.

### Start the app

1. Double-click `VanishCam.exe`.
2. Choose a mode in the opening menu with the mouse or keys `1`–`4`.
3. **Leave the camera frame for 4 seconds.** VanishCam records the empty background during this time. Wait for the terminal to say that the background is ready, then step back into the frame.
4. Perform the gesture for your mode. Keep the preview window selected when using keyboard shortcuts.

| Mode | How to disappear | How to reappear |
| --- | --- | --- |
| **1 — Normal Vanish** | Raise your index and middle fingers in a V sign. The dissolve lasts about 3.6 seconds. | Press `R`. |
| **2 — Naruto Vanish** | Bring your palms together with fingers side by side, without interlacing them. Keep both hands visible. Smoke and a falling wooden log replace you. | Press `R`. |
| **3 — Particles** | Make the same V sign as in Normal Vanish. Your silhouette breaks into wind-swept particles for about 2.1 seconds. | Press `R`. |
| **4 — Goku** | Hold your straight, joined index and middle fingers against your forehead for **1 second**. | Lower your hand, then repeat the same gesture for **1 second**. `R` is disabled in this mode. |

In Goku mode, the terminal shows a countdown for both disappearance and reappearance. The sound effect plays in both directions. In Naruto mode, the sound plays when you disappear. Sound comes from your computer's audio output.

### Keyboard shortcuts

- `SPACE` — capture a new empty background. Leave the frame for 4 seconds again.
- `R` — reappear in Normal Vanish, Naruto Vanish, or Particles.
- `V` — start the selected effect manually in Normal Vanish, Naruto Vanish, or Particles.
- `F` — toggle fullscreen.
- `Q` or `ESC` — quit.

`V` and `R` do not work in Goku mode. Press shortcuts while the preview window is selected.

### Use VanishCam in a video call

1. Install OBS Studio, which provides the **OBS Virtual Camera** driver.
2. Make sure OBS's **Start Virtual Camera** function is **off** before launching VanishCam. VanishCam tries to use that virtual camera automatically.
3. Start VanishCam and check the terminal for a message confirming the virtual camera output.
4. In your video-call app, select **OBS Virtual Camera** as the camera.

The virtual camera carries video. To include the sound effects in a call or stream, configure that app to capture your computer's audio output as well.

### Use VanishCam inside an OBS scene

If you want OBS itself to produce its virtual camera, open PowerShell in the folder containing the EXE and run:

```powershell
.\VanishCam.exe --no-virtual-camera
```

In OBS, add a **Window Capture** source and select **Webcam - Anteprima**. You can then start OBS's virtual camera. OBS Virtual Camera cannot be both VanishCam's output and OBS's output at the same time.

### If something does not work

- **You remain visible or the background looks wrong:** press `SPACE`, step completely out of view for 4 seconds, and try again. Keep the camera still.
- **The gesture is not recognized:** improve the lighting and keep your hands fully inside the frame. For Goku, place two joined, straight fingers at your forehead and hold them for the full second.
- **The webcam will not open:** close other apps using the camera and check Windows camera permissions. If you have more than one camera, open PowerShell in the EXE folder and run `.\VanishCam.exe --camera 1`.
- **The virtual camera is unavailable:** install OBS Studio, stop OBS's virtual camera, and restart VanishCam. You can still use the local preview without a virtual camera.
- **Video lags:** close other camera-heavy apps. From PowerShell in the EXE folder, run `.\VanishCam.exe --width 640 --height 360 --fps 24` to reduce the workload.

VanishCam processes the video locally. It does not record or upload your webcam feed.

---

## Italiano

### Cosa serve

- Un PC Windows e una webcam funzionante.
- `VanishCam.exe`. Non occorre installare Python.
- Facoltativo: OBS Studio con OBS Virtual Camera per usare l'effetto nelle videochiamate o nelle app di streaming.

Per un risultato migliore, tieni ferma la webcam, usa una luce uniforme ed evita movimenti sullo sfondo.

### Avvio

1. Fai doppio clic su `VanishCam.exe`.
2. Scegli una modalità nel menu iniziale con il mouse oppure con i tasti `1`–`4`.
3. **Esci completamente dall'inquadratura per 4 secondi.** In questo intervallo VanishCam acquisisce lo sfondo vuoto. Aspetta che il terminale segnali che lo sfondo è pronto, poi rientra.
4. Esegui il gesto della modalità scelta. Per usare i tasti, tieni selezionata la finestra di anteprima.

| Modalità | Come sparire | Come riapparire |
| --- | --- | --- |
| **1 — Normal Vanish** | Alza indice e medio formando una V. La dissolvenza dura circa 3,6 secondi. | Premi `R`. |
| **2 — Naruto Vanish** | Unisci i palmi con le dita affiancate, senza intrecciarle. Tieni entrambe le mani visibili. Al tuo posto compaiono fumo e un tronco che cade. | Premi `R`. |
| **3 — Particles** | Fai lo stesso segno a V di Normal Vanish. La sagoma si disperde in particelle trasportate dal vento per circa 2,1 secondi. | Premi `R`. |
| **4 — Goku** | Tieni indice e medio distesi, uniti e appoggiati alla fronte per **1 secondo**. | Abbassa la mano e ripeti lo stesso gesto per **1 secondo**. In questa modalità `R` è disattivato. |

In modalità Goku, il terminale mostra il conto alla rovescia sia per la sparizione sia per la riapparizione. L'audio parte in entrambi i casi. In modalità Naruto, l'audio parte quando sparisci. I suoni escono dagli altoparlanti del computer.

### Comandi da tastiera

- `SPAZIO` — acquisisce un nuovo sfondo vuoto. Esci di nuovo dall'inquadratura per 4 secondi.
- `R` — ti fa riapparire in Normal Vanish, Naruto Vanish o Particles.
- `V` — avvia manualmente l'effetto scelto in Normal Vanish, Naruto Vanish o Particles.
- `F` — attiva o disattiva lo schermo intero.
- `Q` o `ESC` — chiude l'app.

I tasti `V` e `R` non funzionano in modalità Goku. Premi i comandi mentre è selezionata la finestra di anteprima.

### Uso nelle videochiamate

1. Installa OBS Studio, che fornisce il driver **OBS Virtual Camera**.
2. Prima di aprire VanishCam, verifica che la funzione **Avvia fotocamera virtuale** di OBS sia **disattivata**. VanishCam prova a usare automaticamente quella webcam virtuale.
3. Avvia VanishCam e controlla nel terminale il messaggio che conferma l'uscita virtuale.
4. Nell'app di videochiamata scegli **OBS Virtual Camera** come webcam.

La webcam virtuale trasmette il video. Per includere gli effetti sonori in una chiamata o diretta, configura l'app anche per acquisire l'audio del computer.

### Uso in una scena OBS

Se vuoi che sia OBS a produrre la webcam virtuale, apri PowerShell nella cartella dell'EXE e avvia:

```powershell
.\VanishCam.exe --no-virtual-camera
```

In OBS aggiungi una sorgente **Cattura finestra** e seleziona **Webcam - Anteprima**. A quel punto puoi avviare la fotocamera virtuale da OBS. OBS Virtual Camera non può essere contemporaneamente l'uscita di VanishCam e quella di OBS.

### Se qualcosa non funziona

- **Rimani visibile o lo sfondo è sbagliato:** premi `SPAZIO`, esci completamente dall'inquadratura per 4 secondi e riprova. Non spostare la webcam.
- **Il gesto non viene riconosciuto:** migliora l'illuminazione e tieni le mani interamente nell'inquadratura. In Goku, appoggia due dita distese e unite alla fronte per un secondo intero.
- **La webcam non si apre:** chiudi le altre app che la usano e controlla le autorizzazioni della fotocamera in Windows. Se hai più webcam, apri PowerShell nella cartella dell'EXE e prova `.\VanishCam.exe --camera 1`.
- **La webcam virtuale non è disponibile:** installa OBS Studio, ferma la sua fotocamera virtuale e riavvia VanishCam. Puoi comunque usare l'anteprima locale.
- **Il video va a scatti:** chiudi le altre app che usano molto la webcam. Da PowerShell nella cartella dell'EXE, avvia `.\VanishCam.exe --width 640 --height 360 --fps 24` per ridurre il carico.

VanishCam elabora il video sul tuo computer. Non registra né carica online il flusso della webcam.
