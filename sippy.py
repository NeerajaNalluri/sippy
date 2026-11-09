"""
Sippy - your little hydration buddy.

A cute girl (Neeru) or boy (Nani) walks across the bottom of your screen,
on top of whatever app you are using, holding a water bottle and reminds
you to drink water.

  * "Thank you!" -> takes a happy sip, hearts pop, walks off to the other side.
                    Comes back after `remind_every_minutes`.
  * "Later"      -> sad face, walks back the way they came.
                    Comes back after `snooze_minutes` (default 5).

The buddy is the opposite gender to the name in your Windows user name: a girl's
name gets Nani (boy), a boy's name gets Neeru (girl). Override in config.json.
If images/<buddy>_*.png photos exist they are used instead of the drawing.
Right-click the buddy to quit. Only uses the Python standard library.
"""

import argparse
import ctypes
import ctypes.wintypes
import datetime
import getpass
import json
import math
import os
import random
import re
import sys
import time
import tkinter as tk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PID_PATH = os.path.join(APP_DIR, "sippy.pid")
IMG_DIR = os.path.join(APP_DIR, "images")   # optional photos: <kind>_<pose>.png

DEFAULT_CONFIG = {
    "your_name": "",              # empty = read it from Windows
    "buddy": "auto",              # auto | girl | boy
    "remind_every_minutes": 45,   # after you say "Thank you!"
    "snooze_minutes": 5,          # after you say "Later"
    "first_reminder_after_seconds": 5,
    "sound": True,
}

BUDDY_NAMES = {"girl": "Neeru", "boy": "Nani"}

# ---------------------------------------------------------------- name logic

GIRL_NAMES = {
    # Indian
    "lakshmi", "neeraja", "priya", "divya", "kavya", "sneha", "anjali", "pooja",
    "deepika", "swathi", "swati", "sravani", "sravya", "harika", "keerthi",
    "bhavana", "sowmya", "soumya", "ramya", "lavanya", "madhuri", "meena",
    "sita", "geetha", "gita", "radha", "anusha", "aishwarya", "nandini",
    "shruti", "sruthi", "pavani", "tejaswi", "mounika", "sindhu", "padma",
    "vani", "usha", "asha", "jyothi", "jyoti", "latha", "sirisha", "spandana",
    "chandana", "manasa", "navya", "hema", "rekha", "sunitha", "anitha",
    "kalyani", "sai", "pallavi", "neha", "riya", "isha", "tanvi", "aditi",
    "kiran", "shreya", "nisha", "ritu", "sana", "zara", "fatima", "ayesha",
    "neeru", "anu", "bindu", "indu", "renu", "meenu", "neelu", "shalu", "chinmayi",
    # Western
    "mary", "sarah", "emma", "olivia", "sophia", "emily", "jessica", "jennifer",
    "linda", "susan", "karen", "nancy", "lisa", "amy", "anna", "kate", "grace",
    "chloe", "lucy", "ella", "mia", "ava", "zoe", "ruth", "alice", "rachel",
    "elizabeth", "megan", "hannah", "laura", "julia", "rose", "jane", "beth",
}
BOY_NAMES = {
    # Indian (many end in a / i, so list them explicitly)
    "krishna", "rama", "ram", "surya", "ravi", "hari", "shiva", "siva", "vishnu",
    "arjuna", "arjun", "rahul", "rohit", "amit", "ajay", "vijay", "sanjay",
    "kumar", "raju", "ramesh", "suresh", "mahesh", "naresh", "rajesh", "dinesh",
    "ganesh", "venkat", "venkata", "srinivas", "srinivasa", "chandu", "chandra",
    "chandrasekhar", "shankar", "sankar", "prasad", "satya", "teja", "aditya",
    "nikhil", "akhil", "karthik", "manoj", "anil", "sunil",
    "praveen", "naveen", "pavan", "kalyan", "vamsi", "vamshi",
    "balaji", "murali", "gopi", "ravi teja", "harsha", "yash", "dev", "aman",
    "mohan", "mohammed", "mohammad", "ali", "imran", "farhan", "sami",
    # Western
    "john", "james", "robert", "michael", "william", "david", "richard", "joseph",
    "thomas", "charles", "daniel", "matthew", "andy", "tony", "harry", "jerry",
    "gary", "barry", "henry", "jimmy", "bobby", "billy", "eddie", "luca",
    "noah", "joshua", "elijah", "jamie", "toby", "rory", "joey", "mark", "paul",
}


def windows_display_name():
    """Full name from Windows (e.g. 'Neeru'), if available."""
    try:
        get_name = ctypes.windll.secur32.GetUserNameExW
        size = ctypes.c_ulong(0)
        get_name(3, None, ctypes.byref(size))  # 3 = NameDisplay
        if size.value:
            buf = ctypes.create_unicode_buffer(size.value)
            if get_name(3, buf, ctypes.byref(size)):
                return buf.value
    except Exception:
        pass
    return ""


def first_name(raw):
    """'LakshmiNeerajaNallur' -> 'Lakshmi', 'john.doe' -> 'John', 'Doe, Jane' -> 'Jane'."""
    raw = (raw or "").strip()
    if "," in raw:  # "Last, First" style directory names
        raw = raw.split(",", 1)[1]
    tokens = [t for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", raw) if len(t) >= 2]
    return tokens[0].capitalize() if tokens else "Friend"


def guess_buddy(name):
    n = name.lower()
    if n in GIRL_NAMES:
        return "girl"
    if n in BOY_NAMES:
        return "boy"
    # Simple heuristic: many female names end with these sounds
    if n.endswith(("a", "i", "ee", "ini", "shree", "shri", "vi")):
        return "girl"
    return "boy"


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception as exc:
            print("config.json could not be read, using defaults:", exc)
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(DEFAULT_CONFIG, fh, indent=2)
    return cfg


def work_area(root):
    """Screen area without the taskbar: (left, top, right, bottom)."""
    try:
        r = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
        if r.right > r.left:
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48


# ---------------------------------------------------------------- drawing

KEY = "#ff00fe"          # this colour becomes fully transparent
W, H = 470, 330          # window size
CHAR_X = 95              # character centre inside the window
FRAME_MS = 30
WALK_PX = 28             # pixels moved per walk-cycle frame (photo buddies)

SKIN, SKIN_LINE = "#ffd9b8", "#d9a07c"
INK = "#2b2b2b"
FONT = "Segoe UI"

LOOKS = {
    "girl": {"hair": "#5a3825", "outfit": "#ff8fb8", "outfit_line": "#e0608f",
             "shoe": "#ff4f8b", "accent": "#ff4f8b"},
    "boy": {"hair": "#3b2a20", "outfit": "#58a6ff", "outfit_line": "#2f7ad6",
            "shoe": "#444a55", "accent": "#2f4b7c"},
}


def round_rect(c, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def rotated(cx, cy, pts, angle_deg):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        out += [cx + x * ca - y * sa, cy + x * sa + y * ca]
    return out


def water_drop(c, x, y, s, fill="#4fb6f5"):
    c.create_polygon(x, y - s * 1.6, x - s, y, x + s, y, fill=fill, outline="")
    c.create_oval(x - s, y - s, x + s, y + s, fill=fill, outline="")
    c.create_oval(x - s * 0.5, y - s * 0.4, x - s * 0.1, y, fill="white", outline="")


# ---------------------------------------------------------------- the app

class Sippy:
    def __init__(self, cfg, demo=False):
        self.cfg = cfg
        raw_name = cfg.get("your_name") or windows_display_name() or getpass.getuser()
        self.user = first_name(raw_name)
        buddy = cfg.get("buddy", "auto")
        if buddy in ("girl", "boy"):
            self.kind = buddy
        else:
            # buddy is the opposite gender: girls get a boy, boys get a girl
            self.kind = "boy" if guess_buddy(self.user) == "girl" else "girl"
        self.buddy_name = BUDDY_NAMES[self.kind]
        self.look = LOOKS[self.kind]

        if demo:
            self.interval_ms = 30_000
            self.snooze_ms = 15_000
            self.first_ms = 1_500
        else:
            self.interval_ms = int(float(cfg["remind_every_minutes"]) * 60_000)
            self.snooze_ms = int(float(cfg["snooze_minutes"]) * 60_000)
            self.first_ms = int(float(cfg["first_reminder_after_seconds"]) * 1000)
        self.snooze_label = self._label(self.snooze_ms)

        self.root = tk.Tk()
        self.root.title("Sippy")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.config(bg=KEY)
        self.c = tk.Canvas(self.root, width=W, height=H, bg=KEY, highlightthickness=0)
        self.c.pack()
        self.c.bind("<Button-1>", self.on_click)
        self.c.bind("<Motion>", self.on_motion)
        self.c.bind("<Button-3>", self.on_menu)
        self.photos = self.load_photos()
        self.walk = self.load_walk() if self.photos else {}
        # sad walk after "Later"; falls back to the normal walk if missing
        self.walk_sad = (self.load_walk("walksad") if self.walk else {}) or self.walk
        self.walk_dist = 0.0

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Quit Sippy", command=self.quit)

        self.left, self.top, self.right, self.bottom = work_area(self.root)
        self.y = self.bottom - H
        self.x = self.left - W
        self.target_x = self.left + (self.right - self.left - W) // 2

        self.state = "hidden"
        self.state_t = time.time()
        self.facing = 1
        self.phase = 0.0
        self.mood = "normal"
        self.bubble = None
        self.buttons = {}
        self.hearts = []
        self.next_blink = time.time() + 3
        self.glasses = 0
        self.today = datetime.date.today()
        self.job = None

        self.root.withdraw()
        print(f"Sippy started: hi {self.user}! Your buddy is {self.buddy_name} ({self.kind}).")
        print(f"First reminder in {self._label(self.first_ms)}, then every "
              f"{self._label(self.interval_ms)}; 'Later' snoozes {self.snooze_label}.")
        self.schedule(self.first_ms)
        self.tick()

    # ---------- helpers
    @staticmethod
    def _label(ms):
        secs = round(ms / 1000)
        if secs < 60:
            return f"{secs} seconds"
        mins = round(secs / 60)
        return f"{mins} minute" + ("" if mins == 1 else "s")

    def load_photos(self):
        """Real photos for this buddy, if images/<kind>_<pose>.png all exist."""
        photos = {}
        for pose in ("normal", "drink", "sad"):
            path = os.path.join(IMG_DIR, f"{self.kind}_{pose}.png")
            if not os.path.exists(path):
                return {}
            try:
                photos[pose] = tk.PhotoImage(master=self.root, file=path)
            except tk.TclError:
                return {}
        return photos

    def load_walk(self, name="walk"):
        """Walk-cycle frames images/<kind>_<name>_r0..N.png (right) and _l0..N (left)."""
        frames = {1: [], -1: []}
        for facing, tag in ((1, "r"), (-1, "l")):
            i = 0
            while True:
                path = os.path.join(IMG_DIR, f"{self.kind}_{name}_{tag}{i}.png")
                if not os.path.exists(path):
                    break
                try:
                    frames[facing].append(tk.PhotoImage(master=self.root, file=path))
                except tk.TclError:
                    return {}
                i += 1
        if not frames[1] or len(frames[1]) != len(frames[-1]):
            return {}
        return frames

    def set_state(self, s):
        self.state = s
        self.state_t = time.time()

    def elapsed(self):
        return time.time() - self.state_t

    def schedule(self, ms):
        if self.job:
            self.root.after_cancel(self.job)
        self.job = self.root.after(ms, self.arrive)

    # ---------- life cycle
    def arrive(self):
        self.job = None
        if self.state != "hidden":
            return
        if datetime.date.today() != self.today:
            self.today, self.glasses = datetime.date.today(), 0
        self.left, self.top, self.right, self.bottom = work_area(self.root)
        self.y = self.bottom - H
        self.target_x = self.left + (self.right - self.left - W) // 2
        self.x = self.left - W
        self.facing, self.mood, self.bubble, self.hearts = 1, "normal", None, []
        self.place()
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.set_state("entering")

    def hide(self, next_ms):
        self.root.withdraw()
        self.bubble, self.buttons = None, {}
        self.set_state("hidden")
        self.schedule(next_ms)

    def place(self):
        self.root.geometry(f"{W}x{H}+{int(self.x)}+{int(self.y)}")

    def tick(self):
        if self.state != "hidden":
            self.update()
            self.place()
            self.draw()
        self.root.after(FRAME_MS, self.tick)

    def update(self):
        start_x = self.x
        self._update()
        self.walk_dist += abs(self.x - start_x)

    def _update(self):
        s = self.state
        if s == "entering":
            self.phase += 0.35
            self.x = min(self.x + 5, self.target_x)
            if self.x >= self.target_x:
                self.set_state("asking")
                self.bubble = "ask"
                self.root.attributes("-topmost", True)
                if self.cfg.get("sound", True):
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
        elif s == "asking":
            self.phase = 0
        elif s == "drinking":
            if random.random() < 0.25:
                self.spawn_heart()
            if self.elapsed() > 1.8:
                self.bubble = None
                self.set_state("leaving_happy")
        elif s == "leaving_happy":
            self.phase += 0.45
            self.x += 8
            if random.random() < 0.08:
                self.spawn_heart()
            if self.x > self.right + 10:
                self.hide(self.interval_ms)
                return
        elif s == "sad_talk":
            if self.elapsed() > 2.2:
                self.bubble = None
                self.facing = -1
                self.set_state("leaving_sad")
        elif s == "leaving_sad":
            self.phase += 0.25
            self.x -= 3.5
            if self.x < self.left - W - 10:
                self.hide(self.snooze_ms)
                return

        for h in self.hearts:
            h["y"] -= 1.6
            h["x"] += math.sin(h["y"] / 9) * 0.8
            h["life"] -= 1
        self.hearts = [h for h in self.hearts if h["life"] > 0]

    def spawn_heart(self):
        self.hearts.append({"x": CHAR_X + random.randint(-30, 40),
                            "y": H - (280 if self.photos else 190), "life": random.randint(30, 50),
                            "size": random.randint(11, 18)})

    # ---------- input
    def hit(self, x, y):
        for name, (x0, y0, x1, y1) in self.buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def on_motion(self, e):
        self.c.config(cursor="hand2" if self.hit(e.x, e.y) else "")

    def on_click(self, e):
        if self.state != "asking":
            return
        b = self.hit(e.x, e.y)
        if b == "thanks":
            self.glasses += 1
            self.mood = "happy"
            self.bubble = "thanks"
            self.buttons = {}
            self.set_state("drinking")
        elif b == "later":
            self.mood = "sad"
            self.bubble = "later"
            self.buttons = {}
            self.set_state("sad_talk")

    def on_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def quit(self):
        try:
            os.remove(PID_PATH)
        except OSError:
            pass
        self.root.destroy()

    # ---------- drawing
    def draw(self):
        c = self.c
        c.delete("all")
        self.draw_character()
        for h in self.hearts:
            c.create_text(h["x"], h["y"], text="♥", fill="#ff4f8b",
                          font=(FONT, h["size"], "bold"))
        if self.bubble:
            self.draw_bubble()

    def draw_character(self):
        c, f, L = self.c, self.facing, self.look
        walking = self.state in ("entering", "leaving_happy", "leaving_sad")
        swing = math.sin(self.phase) * 12 if walking else 0
        if self.state == "leaving_happy":
            bounce = abs(math.sin(self.phase)) * 12
        elif walking:
            bounce = abs(math.sin(self.phase)) * 3
        else:
            bounce = 0
        cx, G = CHAR_X, H - 8 - bounce
        hip = G - 66
        drinking = self.state == "drinking"

        if self.photos:
            if drinking:
                pose = "drink"
            elif self.mood == "sad":
                pose = "sad"
            else:
                pose = "normal"
            if walking and self.walk:
                walk = self.walk_sad if self.state == "leaving_sad" else self.walk
                frames = walk[self.facing]
                # advance one frame every WALK_PX pixels so the feet keep pace
                img = frames[int(self.walk_dist / WALK_PX) % len(frames)]
                c.create_image(cx, H - 4, image=img, anchor="s")
            else:
                # no walk frames: gentle side-to-side sway instead
                sway = math.sin(self.phase) * 3 if walking else 0
                c.create_image(cx + sway, G + 4, image=self.photos[pose], anchor="s")
            return

        # back arm
        c.create_line(cx - f * 15, G - 122, cx - f * 24 + swing * 0.6, G - 86,
                      width=8, fill=SKIN, capstyle=tk.ROUND)

        # legs + shoes
        for side, s in ((-1, swing), (1, -swing)):
            lx = cx + side * 9
            fx = lx + s
            c.create_line(lx, hip, fx, G - 10, width=9, fill=SKIN, capstyle=tk.ROUND)
            c.create_oval(fx - 9 + f * 2, G - 15, fx + 9 + f * 2, G - 2,
                          fill=L["shoe"], outline="")

        # hair behind the head (girl: long hair)
        hy = G - 172
        if self.kind == "girl":
            c.create_oval(cx - 41, hy - 40, cx + 41, hy + 54, fill=L["hair"], outline="")

        # neck + body
        c.create_rectangle(cx - 6, G - 142, cx + 6, G - 128, fill=SKIN, outline="")
        if self.kind == "girl":
            c.create_polygon(cx - 17, G - 132, cx + 17, G - 132, cx + 35, G - 60,
                             cx - 35, G - 60, fill=L["outfit"], outline=L["outfit_line"], width=2)
            c.create_line(cx - 30, G - 70, cx + 30, G - 70, fill="white", width=3)
            water_drop(c, cx, G - 102, 6, fill="white")
        else:
            c.create_rectangle(cx - 21, G - 84, cx + 21, G - 62, fill=L["accent"], outline="")
            round_rect(c, cx - 22, G - 132, cx + 22, G - 80, 10,
                       fill=L["outfit"], outline=L["outfit_line"], width=2)
            water_drop(c, cx, G - 104, 6, fill="white")

        # bottle + front arm
        if drinking:
            hand = (cx + f * 30, G - 160)  # bottle is drawn after the face
        else:
            self.draw_bottle(cx + f * 36, G - 114, 0)
            hand = (cx + f * 33, G - 102)
        c.create_line(cx + f * 15, G - 122, hand[0], hand[1], width=8, fill=SKIN,
                      capstyle=tk.ROUND)
        c.create_oval(hand[0] - 6, hand[1] - 6, hand[0] + 6, hand[1] + 6,
                      fill=SKIN, outline=SKIN_LINE)

        # head
        r = 34
        c.create_oval(cx - r, hy - r, cx + r, hy + r, fill=SKIN, outline=SKIN_LINE, width=2)
        c.create_arc(cx - 37, hy - 39, cx + 37, hy + 17, start=0, extent=180,
                     style=tk.CHORD, fill=L["hair"], outline=L["hair"])
        if self.kind == "girl":
            bx, by = cx - f * 22, hy - 33
            c.create_polygon(bx, by, bx - 12, by - 9, bx - 12, by + 9, fill=L["accent"])
            c.create_polygon(bx, by, bx + 12, by - 9, bx + 12, by + 9, fill=L["accent"])
            c.create_oval(bx - 4, by - 4, bx + 4, by + 4, fill="#ff86b0", outline="")
        else:
            c.create_polygon(cx - 8, hy - 36, cx + f * 4, hy - 50, cx + 10, hy - 35,
                             fill=L["hair"], outline=L["hair"])

        self.draw_face(cx + f * 5, hy, drinking)

        # bottle in front of face while drinking
        if drinking:
            self.draw_bottle(cx + f * 38, G - 170, -f * 120)
            c.create_oval(hand[0] - 6, hand[1] - 6, hand[0] + 6, hand[1] + 6,
                          fill=SKIN, outline=SKIN_LINE)

    def draw_face(self, fx, hy, drinking):
        c = self.c
        ey, my = hy + 4, hy + 20
        now = time.time()
        blinking = False
        if now > self.next_blink:
            blinking = True
            if now > self.next_blink + 0.15:
                self.next_blink = now + random.uniform(2.5, 5)

        for side in (-1, 1):
            ex = fx + side * 12
            if self.mood == "happy" or drinking:
                c.create_arc(ex - 6, ey - 3, ex + 6, ey + 9, start=20, extent=140,
                             style=tk.ARC, width=3, outline=INK)
            elif self.mood == "sad":
                c.create_oval(ex - 3.5, ey - 3, ex + 3.5, ey + 5, fill=INK, outline="")
                inner_up = (ex + 6, ey - 13) if side < 0 else (ex - 6, ey - 13)
                outer = (ex - 6, ey - 8) if side < 0 else (ex + 6, ey - 8)
                c.create_line(*outer, *inner_up, width=2, fill=INK)
            elif blinking:
                c.create_line(ex - 5, ey, ex + 5, ey, width=2, fill=INK)
            else:
                c.create_oval(ex - 4, ey - 5, ex + 4, ey + 5, fill=INK, outline="")
                c.create_oval(ex - 1, ey - 3, ex + 1.5, ey - 0.5, fill="white", outline="")
            # blush
            c.create_oval(fx + side * 20 - 6, ey + 8, fx + side * 20 + 6, ey + 14,
                          fill="#ffb3c1", outline="")

        if self.mood == "sad":
            t = (self.elapsed() * 25) % 22
            tx = fx - 14
            c.create_oval(tx - 3, ey + 7 + t, tx + 3, ey + 15 + t, fill="#7fd3ff", outline="")
            c.create_arc(fx - 8, my, fx + 8, my + 12, start=20, extent=140,
                         style=tk.ARC, width=2, outline="#8a4b3a")
        elif drinking:
            c.create_oval(fx - 3, my - 3, fx + 3, my + 3, fill="#8a4b3a", outline="")
        elif self.mood == "happy":
            c.create_arc(fx - 11, my - 10, fx + 11, my + 10, start=180, extent=180,
                         style=tk.CHORD, fill="#e9566f", outline="#8a4b3a", width=2)
        else:
            c.create_arc(fx - 8, my - 8, fx + 8, my + 4, start=200, extent=140,
                         style=tk.ARC, width=2, outline="#8a4b3a")

    def draw_bottle(self, bx, by, angle):
        c = self.c
        body = [(-5, -22), (5, -22), (9, -14), (9, 22), (-9, 22), (-9, -14)]
        water = [(-8, -2), (8, -2), (8, 21), (-8, 21)]
        cap = [(-6, -29), (6, -29), (6, -22), (-6, -22)]
        shine = [(-5, -10), (-3, -10), (-3, 16), (-5, 16)]
        c.create_polygon(rotated(bx, by, body, angle), fill="#e6f7ff", outline="#3a9bd9", width=2)
        c.create_polygon(rotated(bx, by, water, angle), fill="#6cc8ff", outline="")
        c.create_polygon(rotated(bx, by, shine, angle), fill="white", outline="")
        c.create_polygon(rotated(bx, by, cap, angle), fill="#1e6fd9", outline="#15529f")

    def draw_bubble(self):
        c = self.c
        x0, y0, x1, y1 = 185, 12, W - 10, 165
        round_rect(c, x0, y0, x1, y1, 22, fill="white", outline="#9fd6f7", width=3)
        c.create_polygon(x0 + 2, 118, x0 + 2, 146, CHAR_X + 44, 152,
                         fill="white", outline="#9fd6f7", width=3)
        c.create_line(x0 + 1, 121, x0 + 1, 143, fill="white", width=5)
        self.buttons = {}

        if self.bubble == "ask":
            water_drop(c, x0 + 26, y0 + 30, 7)
            c.create_text(x0 + 40, y0 + 26, anchor="w", text=f"Hey {self.user}!",
                          fill="#1b6fa8", font=(FONT, 14, "bold"))
            c.create_text(x0 + 18, y0 + 50, anchor="nw", fill="#333",
                          font=(FONT, 11),
                          text=f"It's {self.buddy_name} here.\nTime for a sip of water!")
            if self.glasses:
                c.create_text(x1 - 16, y0 + 26, anchor="e", fill="#7a8a99",
                              font=(FONT, 9), text=f"{self.glasses} today")
            self.button("thanks", x0 + 15, y1 - 44, x0 + 138, y1 - 12,
                        "Thank you!", "#43b36b", "#2e8f52")
            self.button("later", x0 + 148, y1 - 44, x1 - 15, y1 - 12,
                        "Later", "#ff9f43", "#d97d24")
        elif self.bubble == "thanks":
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 - 6, fill="#2e8f52",
                          font=(FONT, 13, "bold"), justify="center",
                          text=f"Glug glug... yay!\nStay hydrated, {self.user}!")
        elif self.bubble == "later":
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2 - 6, fill="#b5651d",
                          font=(FONT, 12, "bold"), justify="center",
                          text=f"Oh... okay.\nI'll come back in {self.snooze_label}.")

    def button(self, name, x0, y0, x1, y1, label, fill, edge):
        round_rect(self.c, x0, y0, x1, y1, 14, fill=fill, outline=edge, width=2)
        self.c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, fill="white",
                           font=(FONT, 11, "bold"))
        self.buttons[name] = (x0, y0, x1, y1)

    def run(self):
        with open(PID_PATH, "w") as fh:
            fh.write(str(os.getpid()))
        try:
            self.root.mainloop()
        finally:
            try:
                os.remove(PID_PATH)
            except OSError:
                pass


def main():
    p = argparse.ArgumentParser(description="Sippy - your hydration buddy")
    p.add_argument("--demo", action="store_true",
                   help="fast timings: appear now, snooze 15s, re-remind 30s")
    p.add_argument("--buddy", choices=["girl", "boy"], help="force girl or boy buddy")
    p.add_argument("--name", help="override your name")
    args = p.parse_args()

    cfg = load_config()
    if args.buddy:
        cfg["buddy"] = args.buddy
    if args.name:
        cfg["your_name"] = args.name
    Sippy(cfg, demo=args.demo).run()


if __name__ == "__main__":
    main()
