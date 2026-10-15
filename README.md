# Webcam con effetti di sparizione

Il video viene elaborato sul computer e non viene registrato né inviato a un
server. La finestra di anteprima e la webcam virtuale contengono solo il video
e l'effetto, senza menu, istruzioni o altre scritte sovrapposte.

## ☕ Buy me a coffee

Se ti piace il progetto e vuoi supportarlo, puoi offrirmi un caffè tramite [PayPal](https://paypal.me/nicovic17) oppure [Revolut](https://revolut.me/nicoauriemma).


## Download per Windows

[Scarica VanishCam.exe](https://firebasestorage.googleapis.com/v0/b/graficammece-9b254.firebasestorage.app/o/vanish_cam%2FVanishCam.exe?alt=media&token=82017e0a-52b9-420d-88ba-a4640d5e2ffc) e avvialo con un doppio clic. Non serve installare Python.

## Avvio

1. Fai doppio clic su `AVVIA_LOCALE.bat`.
2. Nel menu iniziale scegli **Normal Vanish** o **Naruto Vanish** con il mouse
   oppure con i tasti `1` e `2`.
3. Esci dall'inquadratura per 4 secondi, mentre viene acquisito lo sfondo.
   Il terminale segnala quando puoi rientrare.

## macOS

Su macOS si usa Python 3 e gli script `.sh` al posto dei `.bat`. Da Terminale,
nella cartella del progetto:

```bash
./avvia_locale.sh                 # menu + anteprima locale
./avvia_locale.sh --mode naruto   # avvia direttamente una modalita
./avvia_virtual.sh                # richiede la webcam virtuale (serve OBS)
./avvia_obs.sh                    # solo anteprima, sorgente per una scena OBS
```

Il primo avvio crea un ambiente Python locale (`.venv-local`) e installa le
dipendenze: serve internet solo quella volta.

**Versioni richieste su macOS (Apple Silicon).** Usa **Python 3.12** (con 3.14
`pygame` non ha un pacchetto pronto e fallisce la compilazione) e aggiorna
`mediapipe` alla **1.1.1**: la 1.0.1 pinnata in `requirements.txt` va in crash su Mac
(`Service is unavailable` / `DrishtiMetalHelper`, servizio Metal) quando crea il
riconoscitore di gesti/mani. Dopo aver creato l'ambiente:

```bash
.venv-local/bin/python -m pip install "mediapipe==1.1.1"
```

Il pin 1.0.1 resta per Windows/Linux, dove funziona; solo macOS richiede la 1.1.1.

**Permesso fotocamera.** Alla prima esecuzione macOS chiede di autorizzare
l'accesso alla fotocamera per il Terminale (o per l'app da cui lanci lo script).
Se neghi per errore, riattivalo in **Impostazioni di Sistema > Privacy e
sicurezza > Fotocamera**.

**Anteprima locale vs webcam virtuale.** L'anteprima locale (la finestra con il
video e l'effetto) funziona da sola, senza installare altro. La **webcam
virtuale** su macOS richiede **[OBS Studio](https://obsproject.com/)** installato:
e l'unico driver di fotocamera virtuale supportato su Mac. Con OBS installato,
lascia **ferma** la fotocamera virtuale in OBS e avvia `./avvia_virtual.sh`; nel
programma destinatario (Zoom, Meet, ...) scegli **OBS Virtual Camera**.

Se `pygame` non si installasse, l'audio Naruto puo usare `ffplay`
(`brew install ffmpeg`); con `pygame` presente non serve.


**Normal Vanish:** alza indice e medio a V. La dissolvenza parte al primo
riconoscimento e dura circa 3,6 secondi.

**Naruto Vanish:** unisci i palmi davanti alla webcam, con le dita affiancate e
senza intrecciarle. Tieni visibili entrambe le mani. L'effetto parte al primo
riconoscimento: il corpo svanisce in una nube di fumo, compare un tronco che
cade verso il basso e resta visibile fino a `R`. Non serve un microfono.
La modalità Naruto usa `hand_landmarker.task` per seguire entrambe le mani.
Quando parte la scomparsa, riproduce `assets/vanish.MP3` dagli altoparlanti del
computer. L'audio parte anche usando `V` e può ripartire dopo `R`.

Puoi avviare una modalità senza menu:

```powershell
local_app\AVVIA_LOCALE.bat --mode naruto
local_app\AVVIA_LOCALE.bat --mode normal
```

## Webcam virtuale e OBS

Se è installato [OBS Studio](https://obsproject.com/), l'app prova ad aprire
automaticamente **OBS Virtual Camera**. Il terminale indica il nome del
dispositivo. Per richiedere esplicitamente la webcam virtuale usa
`AVVIA_VIRTUAL.bat`. Nell'app destinataria scegli **OBS Virtual Camera**.
La fotocamera virtuale di OBS deve essere ferma mentre questa app la produce.

Per usare l'effetto in una scena OBS, avvia `AVVIA_OBS.bat`, aggiungi una sorgente
**Cattura finestra** scegliendo **Webcam - Anteprima**, poi avvia la fotocamera
virtuale da OBS. In alternativa puoi usare
[Unity Capture](https://github.com/schellingb/UnityCapture) come sorgente video
virtuale distinta:

```powershell
local_app\AVVIA_VIRTUAL.bat --virtual-backend unitycapture
```

OBS ha una sola webcam virtuale; non usarla simultaneamente come ingresso e
uscita di OBS. Vedi la [documentazione di pyvirtualcam](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras).

## Comandi

- `SPAZIO`: acquisisce nuovamente lo sfondo.
- `R`: fa riapparire la persona.
- `V`: avvia manualmente l'effetto della modalità scelta.
- `F`: attiva o disattiva lo schermo intero.
- `Q` oppure `ESC`: chiude il programma e libera le webcam.

Puoi cambiare webcam, risoluzione e FPS massimi dell'uscita virtuale:

```powershell
local_app\AVVIA_LOCALE.bat --camera 1 --width 1280 --height 720 --fps 30
```

Per diagnosticare il riconoscimento senza scritte nel video, aggiungi
`--gesture-debug`: le informazioni appaiono solo nel terminale.

## Asset visivi

Il [tronco](assets/substitution_log.png) è un'illustrazione originale generata
con ImageGen usando la foto fornita come riferimento visivo. Il fumo è disegnato
in tempo reale da `naruto_effect.py` affinché segua la posizione della persona e
si ridimensioni con il video. Abbiamo esaminato anche uno
[sprite di fumo CC0](https://opengameart.org/content/smoke-sprite-sheet), ma
l'animazione procedurale si adatta meglio al posizionamento dinamico senza un
asset aggiuntivo. Nessun fotogramma o asset dell'anime è incluso nel progetto.

