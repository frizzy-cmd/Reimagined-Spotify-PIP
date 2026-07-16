import tkinter as tk
from tkinter import ttk
import threading
import time
import urllib.request
import urllib.parse
import json
import sounddevice as sd
import numpy as np
import win32gui
import asyncio
import ctypes
from PIL import Image, ImageTk

try:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
    print("All OK for winrt")
except ImportError as e:
    print(f"Not OK for winrt. Error: {e}")

class DraggableModule:
    def __init__(self, title, width, height, x, y, resizable=True, on_resize=None, save_callback=None):
        self.win = tk.Toplevel() if title != "main" else tk.Tk()
        self.win.title(title)
        self.win.overrideredirect(True)
        self.win.wm_attributes("-topmost", True)
        self.win.config(bg='#010101')
        self.win.wm_attributes("-transparentcolor", '#010101')
        
        self.title = title
        self.resizable = resizable
        self.on_resize = on_resize
        self.save_callback = save_callback
        
        # please work.
        saved = self.load_layout_node()
        if saved:
            self.win.geometry(f"{saved['w']}x{saved['h']}+{saved['x']}+{saved['y']}")
        else:
            self.win.geometry(f"{width}x{height}+{x}+{y}")
        
    def setup_bindings(self, target_widget):
        def start_gesture(event):
            self._drag_start_x = event.x_root
            self._drag_start_y = event.y_root
            self._start_x = self.win.winfo_x()
            self._start_y = self.win.winfo_y()
            self._start_w = self.win.winfo_width()
            self._start_h = self.win.winfo_height()

        def apply_drag(event):
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            self.win.geometry(f"+{self._start_x + dx}+{self._start_y + dy}")

        def apply_resize(event):
            if not self.resizable: return
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            nw = max(40, self._start_w + dx)
            nh = max(20, self._start_h + dy)
            self.win.geometry(f"{nw}x{nh}")
            if self.on_resize:
                self.on_resize(nw, nh)

        def end_gesture(event):
            if self.save_callback:
                self.save_callback()

        target_widget.bind("<Button-1>", start_gesture)
        target_widget.bind("<B1-Motion>", apply_drag)
        target_widget.bind("<ButtonRelease-1>", end_gesture)
        
        if self.resizable:
            target_widget.bind("<Button-3>", start_gesture)
            target_widget.bind("<B3-Motion>", apply_resize)
            target_widget.bind("<ButtonRelease-3>", end_gesture)

    def load_layout_node(self):
        try:
            with open("layout_settings.json", "r") as f:
                return json.load(f).get(self.title)
        except Exception:
            return None

class CoolAssDecoShit:
    def __init__(self):
        # i guess
        sw = 1920 
        try:
            r_chk = tk.Tk()
            sw = r_chk.winfo_screenwidth()
            sh = r_chk.winfo_screenheight()
            r_chk.destroy()
        except Exception:
            sh = 1080

        self.bg = '#010101'
        self.acc = "white"
        self.sub = "gray"
        
        self.nbars = 14
        self.bars = np.zeros(self.nbars)
        self.is_playing = False
        self.top_vol = 1.0 
        self.cur_track = ""

        sx = int(sw / 2 - 360)
        sy = int(sh - 130)

        self.clock_mod = DraggableModule("main", 130, 60, sx, sy, resizable=True, on_resize=self.on_clk_resize, save_callback=self.save_all)
        self.root = self.clock_mod.win 
        self.clock_cv = tk.Canvas(self.root, bg=self.bg, bd=0, highlightthickness=0)
        self.clock_cv.pack(fill=tk.BOTH, expand=True)
        self.clock_mod.setup_bindings(self.clock_cv)

        self.art_mod = DraggableModule("art_layer", 60, 60, sx + 145, sy, resizable=True, on_resize=self.on_art_resize, save_callback=self.save_all)
        self.art_box = tk.Frame(self.art_mod.win, bg="black", bd=2)
        self.art_box.pack(fill=tk.BOTH, expand=True)
        self.art_lbl = tk.Label(self.art_box, bg=self.bg, bd=0, highlightthickness=0)
        self.art_lbl.pack(fill=tk.BOTH, expand=True)
        self.art_mod.setup_bindings(self.art_lbl)
        self.fallback_art()

        self.info_mod = DraggableModule("info_layer", 300, 60, sx + 220, sy, resizable=True, on_resize=self.on_inf_resize, save_callback=self.save_all)
        self.info_cv = tk.Canvas(self.info_mod.win, bg=self.bg, bd=0, highlightthickness=0)
        self.info_cv.pack(fill=tk.BOTH, expand=True)
        self.txt1 = "  Syncing.."
        self.txt2 = "  Waiting for stream!"
        self.info_mod.setup_bindings(self.info_cv)

        self.viz_mod = DraggableModule("viz_layer", 140, 60, sx + 535, sy, resizable=False, save_callback=self.save_all)
        self.viz_cv = tk.Canvas(self.viz_mod.win, bg=self.bg, bd=0, highlightthickness=0)
        self.viz_cv.pack(fill=tk.BOTH, expand=True)
        self.viz_mod.setup_bindings(self.viz_cv)

        self.tick_clock()
        self.redraw_text()

        print("OK! Start! media wrker thread")
        threading.Thread(target=self.spin_media_loop, daemon=True).start()
        threading.Thread(target=self.pump_audio_stream, daemon=True).start()
        
        self.render_viz()
        self.root.mainloop()

    def on_clk_resize(self, w, h):
        self.tick_clock()

    def on_art_resize(self, w, h):
        if hasattr(self, 'raw_art'):
            self.draw_art(self.raw_art)

    def on_inf_resize(self, w, h):
        self.redraw_text()

    def save_all(self):
        try:
            cfg = {}
            mods = {"main": self.clock_mod, "art_layer": self.art_mod, "info_layer": self.info_mod, "viz_layer": self.viz_mod}
            for k, m in mods.items():
                cfg[k] = {"x": m.win.winfo_x(), "y": m.win.winfo_y(), "w": m.win.winfo_width(), "h": m.win.winfo_height()}
            with open("layout_settings.json", "w") as f:
                json.dump(cfg, f, indent=4)
        except Exception: pass

    def tick_clock(self):
        s = time.strftime("%I:%M %p")
        if s.startswith("0"): s = s[1:]
        self.clk_str = f"[ {s} ]"
        
        self.clock_cv.delete("all")
        h = self.clock_mod.win.winfo_height()
        x, y = 5, h // 2

        # im too tired to write a real shader loop so just take this shit
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.clock_cv.create_text(x+dx, y+dy, text=self.clk_str, font=("consolas", 14, "bold"), fill="black", anchor="w")
        self.clock_cv.create_text(x, y, text=self.clk_str, font=("consolas", 14, "bold"), fill=self.acc, anchor="w")
        
        self.root.after(1000, self.tick_clock)

    def redraw_text(self):
        self.info_cv.delete("all")
        h = self.info_mod.win.winfo_height()
        
        x1, y1 = 0, int(h * 0.3)
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.info_cv.create_text(x1+dx, y1+dy, text=self.txt1, font=("consolas", 12, "bold"), fill="black", anchor="w")
        self.info_cv.create_text(x1, y1, text=self.txt1, font=("consolas", 12, "bold"), fill=self.acc, anchor="w")
        
        x2, y2 = 0, int(h * 0.7)
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.info_cv.create_text(x2+dx, y2+dy, text=self.txt2, font=("consolas", 9), fill="black", anchor="w")
        self.info_cv.create_text(x2, y2, text=self.txt2, font=("consolas", 9), fill=self.sub, anchor="w")

    def fallback_art(self):
        self.raw_art = Image.new('RGB', (100, 100), color='#0a0a0a')
        self.draw_art(self.raw_art)

    def draw_art(self, img):
        self.raw_art = img
        w = max(10, self.art_mod.win.winfo_width() - 4)
        h = max(10, self.art_mod.win.winfo_height() - 4)
        res = img.resize((w, h), Image.Resampling.LANCZOS)
        self.tk_art = ImageTk.PhotoImage(res)
        self.art_lbl.config(image=self.tk_art)

    def grab_art_meta(self, term):
        print(f"OK! Fetch! Fetch artwork for query '{term}'")
        try:
            q = urllib.parse.quote(term)
            url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=1" # i hate spotify on foenem they locked the api for album covers to premium users
            req = urllib.request.Request(url, headers={'user-agent': 'mozilla/5.0'})
            with urllib.request.urlopen(req) as r:
                res = json.loads(r.read().decode())
                if res['results']:
                    img_url = res['results'][0]['artworkUrl60'].replace('60x60bb', '600x600bb')
                    print(f"ALL OK! Found artwork {img_url}")
                    with urllib.request.urlopen(img_url) as ir:
                        return Image.open(ir)
                print(f"NOT OK! No results return for query.......")
        except Exception as e:
            print(f"NETWORK NOT OK! Failed fetching artwork {e}")
        return None

    def spin_media_loop(self):
        print("ALL OK! Bg thread is OK! Init mult thrd runtime")
        # COINIT_MULTITHREADED = 0x0 stops collisions if windows shifts async states unexpectedly...
        ctypes.windll.ole32.CoInitializeEx(None, 0x0)
        try:
            asyncio.run(self.smtc_loop())
        except Exception as e:
            print(f"CRASH NOT OK! Async loop crash {e}")
        finally:
            ctypes.windll.ole32.CoUninitialize()

    async def smtc_loop(self):
        print("ALL OK! Win SMTC event listener")
        while True:
            try:
                mgr = await SessionManager.request_async()
                if not mgr:
                    print("MAYBE NOT OK! SessionManager request returned None?")
                    await asyncio.sleep(1.0)
                    continue
                
                sess = mgr.get_current_session()
                if not sess:
                    if self.cur_track != "None":
                        print("MAYBE NOT OK! No active media player sess found...")
                        self.cur_track = "None"
                        self.txt1 = "> Media idle"
                        self.txt2 = "  No active media stream"
                        self.root.after(0, self.redraw_text)
                        self.root.after(0, self.fallback_art)
                    await asyncio.sleep(1.0)
                    continue

                meta = await sess.try_get_media_properties_async()
                if meta and meta.title:
                    t, a = meta.title, meta.artist if meta.artist else "Unknown Artist"
                    cmb = f"{t} - {a}"
                    
                    if cmb != self.cur_track:
                        print(f"CHANGE OK! Track caught {cmb}")
                        self.cur_track = cmb
                        
                        st = t.split(" - ")[0].split(" (")[0]
                        if a and a != "Unknown Artist": st += f" {a}"

                        self.txt1 = f"> {t}" if len(t) < 24 else f"> {t[:21]}..."
                        self.txt2 = f"  {a}" if len(a) < 28 else f"  {a[:25]}..."
                        
                        self.root.after(0, self.redraw_text)
                        threading.Thread(target=self.bg_art_job, args=(st,), daemon=True).start()
            except Exception as e:
                print(f"ERROR NOT OK! Exception loop frame {e}")
            await asyncio.sleep(0.8)

    def bg_art_job(self, term):
        ctypes.windll.ole32.CoInitializeEx(None, 0x0)
        try:
            img = self.grab_art_meta(term)
            if img:
                print("ALL OK! Pushing loaded img buf to canva.s")
                self.root.after(0, lambda: self.draw_art(img))
            else:
                self.root.after(0, self.fallback_art)
        except Exception as e:
            print(f"ERROR NOT OK! Failed applying artwork asset {e}")
            self.root.after(0, self.fallback_art)
        finally:
            ctypes.windll.ole32.CoUninitialize()

    def pump_audio_stream(self):
        dev_idx = None
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev['max_input_channels'] > 0 and 'loopback' in dev['name'].lower():
                    dev_idx = idx
                    break
            if dev_idx is None: dev_idx = sd.default.device[0]
        except Exception:
            dev_idx = None

        def callback(indata, frames, time, status):
            if status and 'input overflow' not in str(status).lower(): return
            v = np.max(np.abs(indata)) * 100
            if v > 0.15:
                self.is_playing = True
                if v > self.top_vol:
                    self.top_vol = v
                else:
                    self.top_vol = max(0.5, self.top_vol * 0.98) 
                
                mh = max(10, self.viz_mod.win.winfo_height() - 5)
                bh = (v / self.top_vol) * mh
                
                nb = []
                for i in range(self.nbars):
                    nb.append(min(bh * np.random.uniform(0.4, 1.1), mh))
                self.bars = [max(o * 0.3, n) for o, n in zip(self.bars, nb)]
            else:
                self.is_playing = False

        try:
            with sd.InputStream(callback=callback, channels=2, blocksize=1024, device=dev_idx):
                while True: time.sleep(1)
        except Exception:
            while True: time.sleep(1)

    def render_viz(self):
        self.viz_cv.delete("all")
        w = self.viz_mod.win.winfo_width()
        h = self.viz_mod.win.winfo_height()
        bw = w / self.nbars

        for i in range(self.nbars):
            val = max(self.bars[i], 4) 
            xc = i * bw + (bw / 2)
            yb, yt = h - 2, h - val
            
            # oooh glowwyyyyyy
            self.viz_cv.create_line(xc, yb, xc, yt, fill='black', width=max(1, bw - 1), capstyle="round")
            self.viz_cv.create_line(xc, yb, xc, yt, fill='white', width=max(1, bw - 5), capstyle="round")
            
        if not self.is_playing:
            self.bars = [max(x - 5, 0) for x in self.bars]
            
        self.root.after(16, self.render_viz)

if __name__ == "__main__":
    CoolAssDecoShit()
