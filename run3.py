import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pyvirtualcam

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision


BASE_DIR = Path(__file__).resolve().parent
FACE_MODEL_PATH = BASE_DIR / "face_landmarker.task"
HAND_MODEL_PATH = BASE_DIR / "hand_landmarker.task"
MEME_PATH = BASE_DIR / "memes" / "image.png"
# YUTA_MEME_PATH disabilitato: la relativa posa non viene caricata o rilevata.
HEARING_MEME_PATH = BASE_DIR / "memes" / "hearing.png"
MEMEOMG_PATH = BASE_DIR / "memes" / "memeomg.png"
SAD_MEME_PATH = BASE_DIR / "memes" / "sad.png"
ME_MEME_PATH = BASE_DIR / "memes" / "me.png"
STOP_MEME_PATH = BASE_DIR / "memes" / "stop.png"
CALMA_MEME_PATH = BASE_DIR / "memes" / "calma.jpg"
OK_MEME_PATH = BASE_DIR / "memes" / "memeok.jpg"

WINDOW_NAME = "Meme Pose Tracker"
CAMERA_WIDTH = 960
CAMERA_HEIGHT = 540
CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720
VIRTUAL_CAMERA_FPS = 30

# Indici MediaPipe delle parti principali della mano.
WRIST = 0
PALM_INDICES = (0, 5, 9, 13, 17)
FINGERTIP_INDICES = (8, 12, 16, 20)


def load_meme(path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Impossibile leggere l'immagine: {path}")
    return image


def open_camera(index=0):
    """Apre la webcam provando i backend Windows e attende il primo frame."""
    backends = (
        ("DirectShow", cv2.CAP_DSHOW),
        ("Media Foundation", cv2.CAP_MSMF),
        ("automatico", cv2.CAP_ANY),
    )
    attempts = []

    for backend_name, backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            attempts.append(f"{backend_name}: non disponibile")
            cap.release()
            continue

        # 1280x720 e una modalita molto piu comune di 960x540. Il frame viene
        # ridimensionato solo dopo l'acquisizione, per la visualizzazione.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)

        for _ in range(30):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                print(f"[WEBCAM] Backend attivo: {backend_name}")
                return cap, frame
            time.sleep(0.05)

        attempts.append(f"{backend_name}: aperta, ma nessun frame ricevuto")
        cap.release()

    details = "; ".join(attempts)
    raise RuntimeError(
        "Non riesco a ricevere immagini dalla webcam. "
        "Chiudi eventuali programmi che la stanno usando e controlla i permessi "
        f"di Windows. Tentativi: {details}"
    )


def face_bounding_box(face_landmarks):
    xs = [landmark.x for landmark in face_landmarks]
    ys = [landmark.y for landmark in face_landmarks]
    return min(xs), min(ys), max(xs), max(ys)


def hand_features(hand_landmarks):
    palm_x = float(np.mean([hand_landmarks[i].x for i in PALM_INDICES]))
    palm_y = float(np.mean([hand_landmarks[i].y for i in PALM_INDICES]))
    fingertip_y = float(np.mean([hand_landmarks[i].y for i in FINGERTIP_INDICES]))

    xs = [landmark.x for landmark in hand_landmarks]
    ys = [landmark.y for landmark in hand_landmarks]

    return {
        "landmarks": hand_landmarks,
        "center": (palm_x, palm_y),
        "wrist_y": hand_landmarks[WRIST].y,
        "fingertip_y": fingertip_y,
        "bbox": (min(xs), min(ys), max(xs), max(ys)),
    }


def hands_on_face_pose(hands, face_box):
    """Riconosce due mani verticali e ravvicinate davanti al volto."""
    if len(hands) < 2 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2

    features = sorted(
        (hand_features(hand) for hand in hands[:2]),
        key=lambda item: item["center"][0],
    )

    valid_hands = []
    overlap_scores = []

    for hand in features:
        center_x, center_y = hand["center"]
        landmarks = hand["landmarks"]

        center_near_face = (
            fx1 - 0.20 * face_width <= center_x <= fx2 + 0.20 * face_width
            and fy1 + 0.18 * face_height <= center_y <= fy2 + 0.35 * face_height
        )

        # Nel gesto di riferimento le dita sono sopra al polso.
        vertical_hand = hand["wrist_y"] - hand["fingertip_y"] >= 0.08 * face_height

        points_near_face = sum(
            fx1 - 0.18 * face_width <= landmark.x <= fx2 + 0.18 * face_width
            and fy1 - 0.08 * face_height <= landmark.y <= fy2 + 0.35 * face_height
            for landmark in landmarks
        )
        overlap = points_near_face / len(landmarks)

        open_hand = extended_finger_count(landmarks) >= 3
        valid_hands.append(
            center_near_face
            and vertical_hand
            and overlap >= 0.45
            and open_hand
        )
        overlap_scores.append(overlap)

    left_hand, right_hand = features
    left_x = left_hand["center"][0]
    right_x = right_hand["center"][0]
    horizontal_gap = (right_x - left_x) / face_width

    # Le mani devono stare ai due lati della zona centrale del volto.
    balanced = (
        left_x <= face_center_x + 0.16 * face_width
        and right_x >= face_center_x - 0.16 * face_width
    )
    close_together = 0.04 <= horizontal_gap <= 0.90

    score = float(np.mean(overlap_scores))
    matched = all(valid_hands) and balanced and close_together
    return matched, score


def extended_finger_states(landmarks):
    """Restituisce lo stato di indice, medio, anulare e mignolo."""
    wrist = np.array([landmarks[WRIST].x, landmarks[WRIST].y])
    states = []
    for tip_index, pip_index in ((8, 6), (12, 10), (16, 14), (20, 18)):
        tip = np.array([landmarks[tip_index].x, landmarks[tip_index].y])
        pip = np.array([landmarks[pip_index].x, landmarks[pip_index].y])
        states.append(
            np.linalg.norm(tip - wrist) >= 1.18 * np.linalg.norm(pip - wrist)
        )
    return states


def extended_finger_count(landmarks):
    """Conta indice, medio, anulare e mignolo visibilmente distesi."""
    return sum(extended_finger_states(landmarks))


def thumbs_up_pose(hands, face_box):
    """Riconosce una mano chiusa con il solo pollice disteso verso l'alto."""
    if not hands or face_box is None:
        return False, 0.0

    # Valuta ogni mano separatamente: il gesto deve funzionare anche quando
    # MediaPipe vede una seconda mano che non sta facendo il pollice alzato.
    if len(hands) > 1:
        results = [thumbs_up_pose([hand], face_box) for hand in hands]
        return max(results, key=lambda result: (result[0], result[1]))

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2

    hand = hand_features(hands[0])
    landmarks = hand["landmarks"]
    palm_x, palm_y = hand["center"]

    wrist = np.array([landmarks[WRIST].x, landmarks[WRIST].y])
    thumb_mcp = np.array([landmarks[2].x, landmarks[2].y])
    thumb_ip = np.array([landmarks[3].x, landmarks[3].y])
    thumb_tip = np.array([landmarks[4].x, landmarks[4].y])
    middle_mcp = np.array([landmarks[9].x, landmarks[9].y])
    palm_scale = max(0.001, float(np.linalg.norm(middle_mcp - wrist)))

    thumb_axis = thumb_tip - thumb_mcp
    thumb_length = float(np.linalg.norm(thumb_axis))
    thumb_rise = float(thumb_mcp[1] - thumb_tip[1])
    thumb_points_up = (
        thumb_tip[1] < thumb_ip[1] < thumb_mcp[1]
        and thumb_rise >= 0.48 * palm_scale
        and abs(thumb_axis[0]) <= 0.78 * thumb_rise
    )

    # I due segmenti del pollice devono essere quasi allineati: cosi una mano
    # chiusa con il pollice ripiegato non viene scambiata per un "OK".
    lower_thumb = thumb_ip - thumb_mcp
    upper_thumb = thumb_tip - thumb_ip
    lower_length = max(0.001, float(np.linalg.norm(lower_thumb)))
    upper_length = max(0.001, float(np.linalg.norm(upper_thumb)))
    thumb_alignment = float(
        np.dot(lower_thumb, upper_thumb) / (lower_length * upper_length)
    )
    thumb_extended = thumb_length >= 0.62 * palm_scale and thumb_alignment >= 0.55

    # Indice, medio, anulare e mignolo devono rimanere ripiegati nel pugno.
    folded_fingers = not any(extended_finger_states(landmarks))

    hx1, hy1, hx2, hy2 = hand["bbox"]
    hand_width = hx2 - hx1
    hand_height = hy2 - hy1
    visible_size = (
        hand_width >= 0.20 * face_width
        and hand_height >= 0.38 * face_height
    )
    near_upper_body = (
        abs(palm_x - face_center_x) <= 1.65 * face_width
        and fy1 - 0.55 * face_height <= palm_y <= fy2 + 1.90 * face_height
    )

    direction_score = min(1.0, max(0.0, thumb_rise / (0.85 * palm_scale)))
    alignment_score = min(1.0, max(0.0, (thumb_alignment + 1.0) / 2.0))
    fold_score = 1.0 if folded_fingers else 0.0
    score = float(np.mean([direction_score, alignment_score, fold_score]))
    matched = (
        thumb_points_up
        and thumb_extended
        and folded_fingers
        and visible_size
        and near_upper_body
    )
    return matched, score


def calma_hand_pose(hands, face_box):
    """Riconosce una mano aperta protesa davanti al petto, col palmo visibile."""
    if len(hands) != 1 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2

    hand = hand_features(hands[0])
    landmarks = hand["landmarks"]
    palm_x, palm_y = hand["center"]
    wrist = np.array([landmarks[WRIST].x, landmarks[WRIST].y])
    fingertip_center = np.mean(
        [[landmarks[i].x, landmarks[i].y] for i in FINGERTIP_INDICES],
        axis=0,
    )
    hand_axis = fingertip_center - wrist

    # Come nella foto, la mano sta davanti alla parte alta del busto e le dita
    # sono rivolte verso l'alto, anche con una moderata inclinazione laterale.
    in_front_of_chest = (
        abs(palm_x - face_center_x) <= 1.05 * face_width
        and fy2 - 0.12 * face_height <= palm_y <= fy2 + 1.65 * face_height
    )
    fingers_above_wrist = (
        hand_axis[1] <= -0.10 * face_height
        and abs(hand_axis[1]) >= 0.42 * abs(hand_axis[0])
    )

    finger_states = extended_finger_states(landmarks)
    four_fingers_open = all(finger_states)

    # Le quattro dita devono puntare pressappoco nella stessa direzione: questo
    # esclude mani molto divaricate o gesti differenti con un palmo aperto.
    finger_directions = []
    for tip_index, mcp_index in ((8, 5), (12, 9), (16, 13), (20, 17)):
        direction = np.array(
            [
                landmarks[tip_index].x - landmarks[mcp_index].x,
                landmarks[tip_index].y - landmarks[mcp_index].y,
            ]
        )
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm <= 0.001:
            return False, 0.0
        finger_directions.append(direction / direction_norm)

    adjacent_alignment = [
        float(np.dot(first, second))
        for first, second in zip(finger_directions, finger_directions[1:])
    ]
    fingers_parallel = min(adjacent_alignment) >= 0.72

    fingertip_xs = [landmarks[i].x for i in FINGERTIP_INDICES]
    knuckle_xs = [landmarks[i].x for i in (5, 9, 13, 17)]
    fingertip_span = max(fingertip_xs) - min(fingertip_xs)
    knuckle_span = max(0.001, max(knuckle_xs) - min(knuckle_xs))
    fingers_together = fingertip_span <= 1.75 * knuckle_span

    hx1, hy1, hx2, hy2 = hand["bbox"]
    hand_width = hx2 - hx1
    hand_height = hy2 - hy1
    visible_and_frontal = (
        hand_width >= 0.34 * face_width
        and hand_height >= 0.48 * face_height
        and knuckle_span >= 0.18 * face_width
    )

    position_score = max(0.0, 1.0 - abs(palm_x - face_center_x) / (1.05 * face_width))
    alignment_score = max(0.0, min(1.0, float(np.mean(adjacent_alignment))))
    size_score = min(1.0, hand_height / (0.78 * face_height))
    score = float(np.mean([position_score, alignment_score, size_score]))
    matched = (
        in_front_of_chest
        and fingers_above_wrist
        and four_fingers_open
        and fingers_parallel
        and fingers_together
        and visible_and_frontal
    )
    return matched, score


def yuta_hand_pose(hands, face_box):
    """Riconosce una mano aperta, grande e distesa davanti al volto."""
    if len(hands) != 1 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    hand = hand_features(hands[0])
    landmarks = hand["landmarks"]
    center_x, center_y = hand["center"]
    hx1, hy1, hx2, hy2 = hand["bbox"]

    center_on_face = (
        fx1 - 0.16 * face_width <= center_x <= fx2 + 0.22 * face_width
        and fy1 + 0.12 * face_height <= center_y <= fy2 + 0.30 * face_height
    )

    points_near_face = sum(
        fx1 - 0.22 * face_width <= landmark.x <= fx2 + 0.25 * face_width
        and fy1 - 0.18 * face_height <= landmark.y <= fy2 + 0.45 * face_height
        for landmark in landmarks
    )
    overlap = points_near_face / len(landmarks)

    hand_width = hx2 - hx1
    hand_height = hy2 - hy1
    large_hand = hand_width >= 0.38 * face_width and hand_height >= 0.55 * face_height
    vertical_hand = hand["wrist_y"] - hand["fingertip_y"] >= 0.10 * face_height

    # Una falange e considerata distesa se la punta e sensibilmente piu
    # lontana dal polso rispetto alla sua articolazione intermedia.
    extended_fingers = extended_finger_count(landmarks)

    fingertip_xs = [landmarks[i].x for i in (4, 8, 12, 16, 20)]
    fingers_spread = max(fingertip_xs) - min(fingertip_xs) >= 0.38 * face_width
    open_hand = extended_fingers >= 3 and fingers_spread

    size_score = min(1.0, hand_height / (0.85 * face_height))
    finger_score = extended_fingers / 4
    score = float(np.mean([overlap, size_score, finger_score]))
    matched = center_on_face and overlap >= 0.50 and large_hand and vertical_hand and open_hand
    return matched, score


def hearing_hand_pose(hands, face_box):
    """Riconosce una mano aperta accanto al volto, all'altezza dell'orecchio."""
    if len(hands) != 1 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    hand = hand_features(hands[0])
    landmarks = hand["landmarks"]
    center_x, center_y = hand["center"]
    hx1, hy1, hx2, hy2 = hand["bbox"]

    # Il palmo deve trovarsi appena oltre uno dei due bordi del viso.
    beside_left_ear = fx1 - 0.70 * face_width <= center_x <= fx1 + 0.08 * face_width
    beside_right_ear = fx2 - 0.08 * face_width <= center_x <= fx2 + 0.70 * face_width
    beside_face = beside_left_ear or beside_right_ear
    ear_height = fy1 + 0.12 * face_height <= center_y <= fy1 + 0.88 * face_height

    hand_width = hx2 - hx1
    hand_height = hy2 - hy1
    large_enough = hand_width >= 0.26 * face_width and hand_height >= 0.42 * face_height
    fingers_up = hand["wrist_y"] - hand["fingertip_y"] >= 0.03 * face_height
    extended_fingers = extended_finger_count(landmarks)
    open_or_cupped = extended_fingers >= 3

    # Almeno parte della mano deve restare vicina al lato della testa.
    near_head_points = sum(
        fx1 - 0.75 * face_width <= landmark.x <= fx2 + 0.75 * face_width
        and fy1 - 0.18 * face_height <= landmark.y <= fy2 + 0.30 * face_height
        for landmark in landmarks
    )
    proximity = near_head_points / len(landmarks)

    size_score = min(1.0, hand_height / (0.75 * face_height))
    finger_score = extended_fingers / 4
    score = float(np.mean([proximity, size_score, finger_score]))
    matched = (
        beside_face
        and ear_height
        and large_enough
        and fingers_up
        and open_or_cupped
        and proximity >= 0.65
    )
    return matched, score


def hands_behind_head_pose(hands, face_box):
    """Riconosce due mani separate ai lati della testa, dietro le orecchie."""
    if len(hands) < 2 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2

    features = sorted(
        (hand_features(hand) for hand in hands[:2]),
        key=lambda item: item["center"][0],
    )
    left_hand, right_hand = features
    left_x, left_y = left_hand["center"]
    right_x, right_y = right_hand["center"]

    left_at_head_side = (
        fx1 - 0.95 * face_width <= left_x <= fx1 + 0.18 * face_width
        and left_x <= face_center_x - 0.24 * face_width
    )
    right_at_head_side = (
        fx2 - 0.18 * face_width <= right_x <= fx2 + 0.95 * face_width
        and right_x >= face_center_x + 0.24 * face_width
    )
    ear_height = all(
        fy1 - 0.18 * face_height <= y <= fy2 + 0.16 * face_height
        for y in (left_y, right_y)
    )
    horizontally_separated = right_x - left_x >= 0.78 * face_width
    vertically_aligned = abs(right_y - left_y) <= 0.48 * face_height

    large_enough = True
    for hand in features:
        hx1, hy1, hx2, hy2 = hand["bbox"]
        hand_width = hx2 - hx1
        hand_height = hy2 - hy1
        if hand_width < 0.22 * face_width and hand_height < 0.32 * face_height:
            large_enough = False

    separation_score = min(1.0, (right_x - left_x) / (1.20 * face_width))
    alignment_score = max(0.0, 1.0 - abs(right_y - left_y) / face_height)
    side_score = float(left_at_head_side and right_at_head_side)
    score = float(np.mean([separation_score, alignment_score, side_score]))
    matched = (
        left_at_head_side
        and right_at_head_side
        and ear_height
        and horizontally_separated
        and vertically_aligned
        and large_enough
    )
    return matched, score


def prayer_hands_pose(hands, face_box):
    """Riconosce due mani giunte o intrecciate, ovunque siano nel frame."""
    if len(hands) < 2:
        return False, 0.0

    features = [hand_features(hand) for hand in hands[:2]]
    first, second = features
    first_x, first_y = first["center"]
    second_x, second_y = second["center"]

    ax1, ay1, ax2, ay2 = first["bbox"]
    bx1, by1, bx2, by2 = second["bbox"]
    first_size = max(ax2 - ax1, ay2 - ay1)
    second_size = max(bx2 - bx1, by2 - by1)
    hand_scale = max(0.001, (first_size + second_size) / 2)

    center_distance = float(np.hypot(first_x - second_x, first_y - second_y))
    centers_close = center_distance <= 1.05 * hand_scale

    # Le aree delle due mani devono toccarsi o essere separate solo da un
    # piccolo spazio, indipendentemente dalla loro posizione rispetto al viso.
    horizontal_distance = max(0.0, max(ax1, bx1) - min(ax2, bx2))
    vertical_distance = max(0.0, max(ay1, by1) - min(ay2, by2))
    boxes_touching = (
        horizontal_distance <= 0.18 * hand_scale
        and vertical_distance <= 0.18 * hand_scale
    )

    # Nelle mani giunte diversi landmark delle due mani finiscono molto vicini.
    # Questo rende il gesto piu semplice senza confonderlo con mani solo affiancate.
    first_points = np.array(
        [[landmark.x, landmark.y] for landmark in first["landmarks"]],
        dtype=np.float32,
    )
    second_points = np.array(
        [[landmark.x, landmark.y] for landmark in second["landmarks"]],
        dtype=np.float32,
    )
    distances = np.linalg.norm(
        first_points[:, np.newaxis, :] - second_points[np.newaxis, :, :],
        axis=2,
    )
    close_threshold = 0.24 * hand_scale
    close_first = int(np.count_nonzero(distances.min(axis=1) <= close_threshold))
    close_second = int(np.count_nonzero(distances.min(axis=0) <= close_threshold))
    landmarks_intertwined = close_first >= 3 and close_second >= 3
    both_hands_open = all(
        extended_finger_count(hand["landmarks"]) >= 3
        for hand in features
    )

    closeness_score = max(0.0, 1.0 - center_distance / (1.05 * hand_scale))
    contact_score = min(1.0, (close_first + close_second) / 12)
    score = float(np.mean([closeness_score, contact_score]))
    matched = (
        centers_close
        and boxes_touching
        and landmarks_intertwined
        and not both_hands_open
    )
    return matched, score


def timeout_hands_pose(hands, face_box):
    """Riconosce due mani aperte e perpendicolari che formano una T."""
    if len(hands) < 2 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2
    features = [hand_features(hand) for hand in hands[:2]]

    axes = []
    for hand in features:
        landmarks = hand["landmarks"]
        wrist = np.array([landmarks[WRIST].x, landmarks[WRIST].y])
        fingertip_center = np.mean(
            [[landmarks[i].x, landmarks[i].y] for i in FINGERTIP_INDICES],
            axis=0,
        )
        axes.append(fingertip_center - wrist)

    first_axis, second_axis = axes
    first_horizontal = abs(first_axis[0]) >= 1.25 * abs(first_axis[1])
    second_horizontal = abs(second_axis[0]) >= 1.25 * abs(second_axis[1])
    first_vertical = abs(first_axis[1]) >= 1.25 * abs(first_axis[0])
    second_vertical = abs(second_axis[1]) >= 1.25 * abs(second_axis[0])
    one_horizontal_one_vertical = (
        (first_horizontal and second_vertical)
        or (second_horizontal and first_vertical)
    )

    first_norm = max(0.001, float(np.linalg.norm(first_axis)))
    second_norm = max(0.001, float(np.linalg.norm(second_axis)))
    cosine = abs(float(np.dot(first_axis, second_axis))) / (first_norm * second_norm)
    perpendicular = cosine <= 0.48

    both_open = all(
        extended_finger_count(hand["landmarks"]) >= 3
        for hand in features
    )

    ax1, ay1, ax2, ay2 = features[0]["bbox"]
    bx1, by1, bx2, by2 = features[1]["bbox"]
    first_size = max(ax2 - ax1, ay2 - ay1)
    second_size = max(bx2 - bx1, by2 - by1)
    hand_scale = max(0.001, (first_size + second_size) / 2)
    horizontal_distance = max(0.0, max(ax1, bx1) - min(ax2, bx2))
    vertical_distance = max(0.0, max(ay1, by1) - min(ay2, by2))
    hands_touching = (
        horizontal_distance <= 0.20 * hand_scale
        and vertical_distance <= 0.20 * hand_scale
    )

    mean_x = float(np.mean([hand["center"][0] for hand in features]))
    mean_y = float(np.mean([hand["center"][1] for hand in features]))
    in_front_of_chest = (
        abs(mean_x - face_center_x) <= 1.10 * face_width
        and fy2 - 0.22 * face_height <= mean_y <= fy2 + 1.80 * face_height
    )

    angle_score = max(0.0, 1.0 - cosine)
    orientation_score = float(one_horizontal_one_vertical)
    open_score = min(
        1.0,
        sum(extended_finger_count(hand["landmarks"]) for hand in features) / 8,
    )
    score = float(np.mean([angle_score, orientation_score, open_score]))
    matched = (
        one_horizontal_one_vertical
        and perpendicular
        and both_open
        and hands_touching
        and in_front_of_chest
    )
    return matched, score


def pointing_at_self_pose(hands, face_box):
    """Riconosce una mano sotto il volto con il solo indice rivolto al petto."""
    if len(hands) != 1 or face_box is None:
        return False, 0.0

    fx1, fy1, fx2, fy2 = face_box
    face_width = max(0.001, fx2 - fx1)
    face_height = max(0.001, fy2 - fy1)
    face_center_x = (fx1 + fx2) / 2

    hand = hand_features(hands[0])
    landmarks = hand["landmarks"]
    palm_x, palm_y = hand["center"]
    wrist_x = landmarks[WRIST].x
    wrist_y = landmarks[WRIST].y
    index_tip_x = landmarks[8].x
    index_tip_y = landmarks[8].y

    finger_states = extended_finger_states(landmarks)
    index_only = finger_states[0] and not any(finger_states[1:])

    # La punta dell'indice deve trovarsi sotto il mento e vicino alla linea
    # centrale del corpo, mentre il polso rimane piu esterno.
    fingertip_at_chest = (
        abs(index_tip_x - face_center_x) <= 0.58 * face_width
        and fy2 - 0.06 * face_height <= index_tip_y <= fy2 + 1.55 * face_height
    )
    palm_below_face = (
        abs(palm_x - face_center_x) <= 0.95 * face_width
        and fy2 - 0.05 * face_height <= palm_y <= fy2 + 1.70 * face_height
    )
    points_inward = (
        abs(index_tip_x - face_center_x)
        <= abs(wrist_x - face_center_x) - 0.035 * face_width
    )
    points_upward = wrist_y - index_tip_y >= 0.035 * face_height

    hx1, hy1, hx2, hy2 = hand["bbox"]
    visible_size = (
        hx2 - hx1 >= 0.24 * face_width
        and hy2 - hy1 >= 0.30 * face_height
    )

    inward_score = max(
        0.0,
        min(
            1.0,
            (abs(wrist_x - face_center_x) - abs(index_tip_x - face_center_x))
            / (0.35 * face_width),
        ),
    )
    center_score = max(0.0, 1.0 - abs(index_tip_x - face_center_x) / face_width)
    finger_score = 1.0 if index_only else 0.0
    score = float(np.mean([inward_score, center_score, finger_score]))
    matched = (
        index_only
        and fingertip_at_chest
        and palm_below_face
        and points_inward
        and points_upward
        and visible_size
    )
    return matched, score


def square_from_hand(hand_landmarks, frame_width, frame_height):
    xs = np.array([landmark.x * frame_width for landmark in hand_landmarks])
    ys = np.array([landmark.y * frame_height for landmark in hand_landmarks])

    center_x = float((xs.min() + xs.max()) / 2)
    center_y = float((ys.min() + ys.max()) / 2)
    side = float(max(xs.max() - xs.min(), ys.max() - ys.min()) * 1.28)
    side = max(side, 72.0)

    x1 = max(0.0, center_x - side / 2)
    y1 = max(0.0, center_y - side / 2)
    x2 = min(float(frame_width - 1), center_x + side / 2)
    y2 = min(float(frame_height - 1), center_y + side / 2)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def update_squares(hand_landmarks, old_squares, frame_width, frame_height):
    ordered_hands = sorted(
        hand_landmarks[:2],
        key=lambda hand: float(np.mean([landmark.x for landmark in hand])),
    )

    new_squares = {}
    for index, hand in enumerate(ordered_hands):
        target = square_from_hand(hand, frame_width, frame_height)
        if index in old_squares:
            target = 0.68 * old_squares[index] + 0.32 * target
        new_squares[index] = target
    return new_squares


def draw_analysis_square(frame, square, label, phase):
    x1, y1, x2, y2 = square.astype(int)
    color = (0, 255, 210)
    dark_color = (0, 110, 90)

    cv2.rectangle(frame, (x1, y1), (x2, y2), dark_color, 1, cv2.LINE_AA)

    corner = max(12, min(28, (x2 - x1) // 5))
    thickness = 3
    segments = (
        ((x1, y1 + corner), (x1, y1), (x1 + corner, y1)),
        ((x2 - corner, y1), (x2, y1), (x2, y1 + corner)),
        ((x1, y2 - corner), (x1, y2), (x1 + corner, y2)),
        ((x2 - corner, y2), (x2, y2), (x2, y2 - corner)),
    )
    for first, middle, last in segments:
        cv2.line(frame, first, middle, color, thickness, cv2.LINE_AA)
        cv2.line(frame, middle, last, color, thickness, cv2.LINE_AA)

    scan_y = y1 + int((y2 - y1) * phase)
    cv2.line(frame, (x1 + 4, scan_y), (x2 - 4, scan_y), color, 1, cv2.LINE_AA)
    cv2.putText(
        frame,
        label,
        (x1, max(24, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
        cv2.LINE_AA,
    )


def resize_contain(image, max_width, max_height):
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height)
    resized = cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return resized


def overlay_meme_on_face(frame, meme, face_box):
    """Sovrappone il meme al volto, mantenendolo dentro al frame video."""
    if face_box is None:
        return

    frame_height, frame_width = frame.shape[:2]
    fx1, fy1, fx2, fy2 = face_box
    face_width = max(1, round((fx2 - fx1) * frame_width))
    face_height = max(1, round((fy2 - fy1) * frame_height))
    center_x = round(((fx1 + fx2) / 2) * frame_width)
    center_y = round(((fy1 + fy2) / 2) * frame_height)

    # L'area e abbastanza grande da coprire il viso senza occupare tutto il video.
    max_width = min(frame_width, round(face_width * 1.70))
    max_height = min(frame_height, round(face_height * 1.50))
    shown = resize_contain(meme, max_width, max_height)
    image_height, image_width = shown.shape[:2]

    destination_x1 = center_x - image_width // 2
    destination_y1 = center_y - image_height // 2
    destination_x2 = destination_x1 + image_width
    destination_y2 = destination_y1 + image_height

    # Ritaglia solamente la parte che eventualmente supera i bordi del frame.
    source_x1 = max(0, -destination_x1)
    source_y1 = max(0, -destination_y1)
    source_x2 = image_width - max(0, destination_x2 - frame_width)
    source_y2 = image_height - max(0, destination_y2 - frame_height)

    destination_x1 = max(0, destination_x1)
    destination_y1 = max(0, destination_y1)
    destination_x2 = min(frame_width, destination_x2)
    destination_y2 = min(frame_height, destination_y2)

    if destination_x1 >= destination_x2 or destination_y1 >= destination_y2:
        return

    frame[destination_y1:destination_y2, destination_x1:destination_x2] = shown[
        source_y1:source_y2,
        source_x1:source_x2,
    ]
    cv2.rectangle(
        frame,
        (destination_x1, destination_y1),
        (destination_x2 - 1, destination_y2 - 1),
        (0, 255, 210),
        2,
        cv2.LINE_AA,
    )


def main():
    memes = {
        "two_hands": load_meme(MEME_PATH),
        "hearing": load_meme(HEARING_MEME_PATH),
        "memeomg": load_meme(MEMEOMG_PATH),
        "sad": load_meme(SAD_MEME_PATH),
        "me": load_meme(ME_MEME_PATH),
        "stop": load_meme(STOP_MEME_PATH),
        "calma": load_meme(CALMA_MEME_PATH),
        "ok": load_meme(OK_MEME_PATH),
    }

    face_options = mp_vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(FACE_MODEL_PATH)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.45,
        min_face_presence_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    hand_options = mp_vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(HAND_MODEL_PATH)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.45,
        min_hand_presence_confidence=0.45,
        min_tracking_confidence=0.45,
    )

    face_landmarker = mp_vision.FaceLandmarker.create_from_options(face_options)
    hand_landmarker = mp_vision.HandLandmarker.create_from_options(hand_options)

    try:
        cap, pending_frame = open_camera(0)
    except Exception:
        face_landmarker.close()
        hand_landmarker.close()
        raise

    try:
        virtual_camera = pyvirtualcam.Camera(
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=VIRTUAL_CAMERA_FPS,
            fmt=pyvirtualcam.PixelFormat.BGR,
            backend="obs",
        )
        print(f"[WEBCAM VIRTUALE] Attiva: {virtual_camera.device}")
    except Exception as exc:
        cap.release()
        face_landmarker.close()
        hand_landmarker.close()
        raise RuntimeError(
            "Non riesco ad avviare OBS Virtual Camera. Chiudi OBS Studio o "
            "disattiva la sua Virtual Camera, quindi riprova."
        ) from exc

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)

    last_face_box = None
    last_face_time = 0.0
    squares = {}
    candidate_pose = None
    candidate_frames = 0
    miss_frames = 0
    active_pose = None
    confidence = 0.0
    start_time = time.monotonic()
    camera_read_failures = 0

    try:
        while True:
            if pending_frame is not None:
                frame = pending_frame
                pending_frame = None
                ok = True
            else:
                ok, frame = cap.read()

            if not ok or frame is None or not frame.size:
                camera_read_failures += 1
                if camera_read_failures < 30:
                    time.sleep(0.03)
                    continue
                raise RuntimeError(
                    "La webcam ha smesso di inviare fotogrammi per circa un secondo."
                )
            camera_read_failures = 0

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int((time.monotonic() - start_time) * 1000)

            face_result = face_landmarker.detect_for_video(mp_image, timestamp_ms)
            hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)

            now = time.monotonic()
            if face_result.face_landmarks:
                last_face_box = face_bounding_box(face_result.face_landmarks[0])
                last_face_time = now
            elif now - last_face_time > 1.2:
                last_face_box = None

            detected_hands = hand_result.hand_landmarks
            squares = update_squares(
                detected_hands,
                squares,
                CAMERA_WIDTH,
                CAMERA_HEIGHT,
            )

            two_hands_match, two_hands_confidence = hands_on_face_pose(
                detected_hands,
                last_face_box,
            )
            calma_match, calma_confidence = calma_hand_pose(
                detected_hands,
                last_face_box,
            )
            hearing_match, hearing_confidence = hearing_hand_pose(
                detected_hands,
                last_face_box,
            )
            memeomg_match, memeomg_confidence = hands_behind_head_pose(
                detected_hands,
                last_face_box,
            )
            sad_match, sad_confidence = prayer_hands_pose(
                detected_hands,
                last_face_box,
            )
            me_match, me_confidence = pointing_at_self_pose(
                detected_hands,
                last_face_box,
            )
            stop_match, stop_confidence = timeout_hands_pose(
                detected_hands,
                last_face_box,
            )
            ok_match, ok_confidence = thumbs_up_pose(
                detected_hands,
                last_face_box,
            )

            # Il pollice alzato ha precedenza: basta che una delle mani faccia
            # il gesto, anche quando una seconda mano e visibile nel frame.
            if ok_match:
                detected_pose = "ok"
                current_confidence = ok_confidence
            elif memeomg_match:
                detected_pose = "memeomg"
                current_confidence = memeomg_confidence
            elif stop_match:
                detected_pose = "stop"
                current_confidence = stop_confidence
            elif calma_match:
                detected_pose = "calma"
                current_confidence = calma_confidence
            elif two_hands_match:
                detected_pose = "two_hands"
                current_confidence = two_hands_confidence
            elif sad_match:
                detected_pose = "sad"
                current_confidence = sad_confidence
            elif me_match:
                detected_pose = "me"
                current_confidence = me_confidence
            elif hearing_match:
                detected_pose = "hearing"
                current_confidence = hearing_confidence
            else:
                detected_pose = None
                current_confidence = max(
                    two_hands_confidence,
                    calma_confidence,
                    hearing_confidence,
                    memeomg_confidence,
                    sad_confidence,
                    me_confidence,
                    stop_confidence,
                    ok_confidence,
                )

            confidence = 0.72 * confidence + 0.28 * current_confidence

            if detected_pose is not None:
                miss_frames = 0
                if detected_pose == candidate_pose:
                    candidate_frames += 1
                else:
                    candidate_pose = detected_pose
                    candidate_frames = 1
            else:
                miss_frames += 1
                candidate_pose = None
                candidate_frames = 0

            required_frames = 2 if candidate_pose == "sad" else 5
            if candidate_pose is not None and candidate_frames >= required_frames:
                active_pose = candidate_pose
            elif miss_frames >= 8:
                active_pose = None

            if active_pose is not None:
                overlay_meme_on_face(
                    frame,
                    memes[active_pose],
                    last_face_box,
                )

            phase = (time.monotonic() * 0.65) % 1.0
            for index, square in squares.items():
                draw_analysis_square(frame, square, f"MANO {index + 1}", phase)

            status_color = (0, 255, 210) if active_pose else (0, 210, 255)
            if active_pose == "hearing":
                status = "POSE ASCOLTO RILEVATA"
            elif active_pose == "calma":
                status = "GESTO CALMA RILEVATO"
            elif active_pose == "memeomg":
                status = "MANI DIETRO LA TESTA RILEVATE"
            elif active_pose == "sad":
                status = "POSE PREGHIERA RILEVATA"
            elif active_pose == "me":
                status = "INDICAZIONE SU DI ME RILEVATA"
            elif active_pose == "stop":
                status = "GESTO TIMEOUT RILEVATO"
            elif active_pose == "ok":
                status = "POLLICE ALZATO RILEVATO"
            elif active_pose == "two_hands":
                status = "POSE DUE MANI RILEVATA"
            else:
                status = "ANALISI MANI..."
            cv2.putText(
                frame,
                status,
                (18, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                status_color,
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "Q/ESC: esci",
                (18, CAMERA_HEIGHT - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (225, 225, 225),
                1,
                cv2.LINE_AA,
            )

            cv2.putText(
                frame,
                f"confidenza: {confidence:.0%}",
                (CAMERA_WIDTH - 185, CAMERA_HEIGHT - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (225, 225, 225),
                1,
                cv2.LINE_AA,
            )

            # Lo stesso frame mostrato a schermo viene pubblicato come webcam.
            virtual_camera.send(frame)
            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):
                break
            virtual_camera.sleep_until_next_frame()

    finally:
        virtual_camera.close()
        cap.release()
        cv2.destroyAllWindows()
        face_landmarker.close()
        hand_landmarker.close()


if __name__ == "__main__":
    main()
