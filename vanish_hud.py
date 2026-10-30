"""Preview-only startup guidance and gesture feedback; never sent to virtual output."""
import math
import cv2

GESTURES = {
    "naruto": "Press both open palms together",
    "goku": "Index + middle together at forehead: hold 1 sec",
}

def guidance(phase, elapsed, ready_age, mode, calibration_seconds, holding=0, latched=False):
    gesture = GESTURES.get(mode, "Show a V sign: index + middle up, other fingers curled")
    if phase == "calibrating":
        remaining = max(0, math.ceil(calibration_seconds - elapsed))
        if remaining:
            return ("STEP OUT OF FRAME" if elapsed < 2 else "STAY OUT - CAPTURING BACKGROUND",
                    "Return only when the green READY message appears", str(remaining), 0)
        return ("STAY OUT - FINISHING BACKGROUND", "Almost ready...", "", 0)
    if phase == "vanished":
        return ("REPEAT HAND SIGN TO REAPPEAR", "Lower your hand first. " + gesture, "", holding)
    if mode == "goku" and phase == "ready" and latched:
        return ("LOWER YOUR HAND TO RESET", "Then repeat the forehead sign for one second", "", 0)
    if mode == "goku" and phase == "ready" and holding > 0 and not latched:
        return ("HOLD THE SIGN STEADY", gesture, f"{max(0, 1-holding):.1f}s", holding)
    if phase == "ready" and ready_age < 7:
        return ("READY - STEP BACK IN AND STAY IN FRAME", gesture,
                str(max(1, math.ceil(7-ready_age))), 0)
    return None

def draw_guidance(frame, message):
    if message is None:
        return frame
    title, detail, badge, progress = message
    h, w = frame.shape[:2]
    scale = w / 1280
    panel_height = max(1, min(h, round(128 * scale)))
    panel = frame[:panel_height]
    panel[:] = (panel.astype("float32") * .20 + (20, 24, 30)).clip(0, 255).astype("uint8")
    green = title.startswith("READY") or "REAPPEAR" in title
    accent = (130, 235, 130) if green else (80, 200, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.rectangle(frame, (0, 0), (max(1, round(5*scale)), panel_height-1), accent, -1)
    cv2.putText(frame, title, (round(24*scale), round(38*scale)), font,
                max(.15, .72*scale), accent, max(1, round(2*scale)), cv2.LINE_AA)
    cv2.putText(frame, detail, (round(24*scale), round(76*scale)), font,
                max(.12, .52*scale), (240, 240, 240), max(1, round(scale)), cv2.LINE_AA)
    if badge:
        cv2.putText(frame, badge, (round(w-115*scale), round(72*scale)), font,
                    max(.2, 1.5*scale), accent, max(1, round(2*scale)), cv2.LINE_AA)
    if progress:
        cv2.rectangle(frame, (round(24*scale), round(100*scale)),
                      (round((24+min(1, progress)*700)*scale), round(108*scale)), accent, -1)
    return frame
