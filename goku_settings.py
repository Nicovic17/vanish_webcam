"""Ask for Goku's shared teleport hold time after the webcam selection."""
from __future__ import annotations

import math
import cv2
import numpy as np


def parse_goku_delay(text: str) -> float:
    value = float(text.strip().replace(',', '.') or '1')
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Inserisci un numero maggiore di zero.')
    return value


def choose_goku_delay(check_license=None) -> float | None:
    title = 'Goku - Tempo del gesto'
    text, selected, error = '1', True, ''
    action = [None]

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONUP and 310 <= y <= 370:
            if 395 <= x <= 670:
                action[0] = 'confirm'
            elif 50 <= x <= 310:
                action[0] = 'cancel'

    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(title, on_mouse)
    try:
        while True:
            if check_license:
                check_license()
            window = np.full((410,720,3),(26,29,34),np.uint8)
            def label(message, position, size=.56, color=(220,230,237)):
                cv2.putText(window,message,position,cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
            label('GOKU - TEMPO DEL GESTO',(50,60),.78)
            label('Quanto mantenere il gesto per sparire o riapparire?',(50,103),.53)
            cv2.rectangle(window,(50,130),(670,200),(48,54,62),-1)
            cv2.rectangle(window,(50,130),(670,200),(111,180,195) if selected else (111,142,153),2)
            label(text or '1 (predefinito)',(70,177),.9)
            label('secondi',(540,175),.6)
            label('Esempi: 0.1, 0.5, 1, 2  |  Invio per confermare',(50,233),.53)
            label('Lo stesso tempo vale per sparizione e riapparizione.',(50,258),.51,(179,195,201))
            if error:
                label(error,(50,289),.50,(120,145,255))
            for x1,x2,caption in ((50,310,'Annulla'),(395,670,'Continua')):
                cv2.rectangle(window,(x1,310),(x2,370),(48,54,62) if x1==50 else (61,113,87),-1)
                label(caption,(x1+72,348),.65)
            cv2.imshow(title,window)
            key = cv2.waitKey(30) & 0xFF
            if key == 27 or action[0] == 'cancel' or cv2.getWindowProperty(title,cv2.WND_PROP_VISIBLE) < 1:
                return None
            if key in (10,13) or action[0] == 'confirm':
                action[0] = None
                try:
                    return parse_goku_delay(text)
                except ValueError:
                    error = 'Inserisci un numero maggiore di zero (es. 0.5).'
                    selected = True
            elif key in (8,127):
                text = '' if selected else text[:-1]
                selected, error = False, ''
            elif key == 1:
                selected = True
            elif key in b'0123456789.,-':
                if selected:
                    text = ''
                if len(text) < 18:
                    text += chr(key)
                selected, error = False, ''
    finally:
        cv2.destroyWindow(title)
