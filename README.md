# 💧 Sippy — your little hydration buddy

A friendly, photo-realistic buddy walks across the bottom of your screen, on top
of any app, holding a water bottle and reminding you to drink water.

The buddy is the opposite gender to your name:

| Your name looks like… | Your buddy |
|---|---|
| a girl's name (e.g. Lakshmi, Neeru) | **Jalu** 👦 (blue shirt, navy chinos) |
| a boy's name | **Neeru** 👧 (pink t-shirt, jeans) |

Photos live in `images/` (`<girl|boy>_normal/drink/sad.png` plus walk frames
`<girl|boy>_walk_r0..5.png` and mirrored `_l0..5.png`). If they're missing,
Sippy falls back to the hand-drawn cartoon.

- **Thank you!** → happy face, drinks, hearts pop, walks off to the other side. Comes back after 45 min.
- **Later** → sad face (with a little tear), walks back. Comes back after **5 minutes**.

## Requirements
Windows + Python 3.8 or newer (Tkinter is included with Python). Nothing else to install.

## Run it
| What | How |
|---|---|
| Start (no console window) | double-click `run_sippy.bat` |
| Quick demo (appears now, short timers) | double-click `demo_sippy.bat` |
| Stop | double-click `stop_sippy.bat`, or right-click the buddy → *Quit Sippy* |
| Start automatically at login | `powershell -ExecutionPolicy Bypass -File install_startup.ps1` |
| Remove from startup | `powershell -ExecutionPolicy Bypass -File uninstall_startup.ps1` |

From a terminal:
```
python sippy.py                 # normal
python sippy.py --demo          # fast timings for testing
python sippy.py --buddy boy     # force Jalu
python sippy.py --name Priya    # override your name
```

## Settings (`config.json`, created on first run)
```json
{
  "your_name": "",                 // empty = taken from Windows
  "buddy": "auto",                 // auto | girl | boy
  "remind_every_minutes": 45,      // after "Thank you!"
  "snooze_minutes": 5,             // after "Later"
  "first_reminder_after_seconds": 5,
  "sound": true
}
```

## How it works
- `tkinter` window with no border, always on top, and a "magic" colour made fully
  transparent (`-transparentcolor`), so only the character and bubble are visible
  and clicks pass through the empty space.
- The buddy is a set of transparent PNG photos (AI-generated): a 6-frame walk
  cycle that advances with distance walked, plus normal / drinking / sad poses.
  Hearts, bubble and buttons are canvas shapes, redrawn every 30 ms.
- The window walks along the bottom of the screen, just above the taskbar.
- Gender guess: first name from your Windows display name → a list of common
  Indian and Western names → a simple name-ending rule → buddy of the opposite
  gender. To pick one yourself, set `buddy` in `config.json` to `girl` or `boy`.
