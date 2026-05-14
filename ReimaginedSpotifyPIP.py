import tkinter as tk
import threading
import time
import urllib.request
import urllib.parse
import json
import sounddevice as sd
import numpy as np
import win32gui
import asyncio
from PIL import Image, ImageTk, ImageGrab, ImageStat

from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager

class DraggableModule:
    """helper class to convert any element into its own separate borderless window with auto-saving"""
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
        
        # Load layout coords if ok, otrw use def passed in
        saved_coords = self.load_layout_node()
        if saved_coords:
            self.win.geometry(f"{saved_coords['w']}x{saved_coords['h']}+{saved_coords['x']}+{saved_coords['y']}")
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
            new_w = max(40, self._start_w + dx)
            new_h = max(20, self._start_h + dy)
            self.win.geometry(f"{new_w}x{new_h}")
            if self.on_resize:
                self.on_resize(new_w, new_h)

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
                data = json.load(f)
                return data.get(self.title)
        except Exception:
            return None

class CoolAssDecoShit:
    def __init__(self):
        screen_width = 1920 # Fallback bound
        try:
            # Dummy init to grab real hw 
            root_check = tk.Tk()
            screen_width = root_check.winfo_screenwidth()
            screen_height = root_check.winfo_screenheight()
            root_check.destroy()
        except Exception:
            screen_height = 1080

        self.bg_color = '#010101'
        self.accent_color = "white"
        self.sub_color = "gray"
        
        self.num_bars = 14
        self.bar_data = np.zeros(self.num_bars)
        self.audio_active = False
        self.max_seen = 1.0 
        self.current_song = ""

        start_x = int(screen_width / 2 - 360)
        start_y = int(screen_height - 130)

# Clock mgr window
        self.clock_mod = DraggableModule("main", 130, 60, start_x, start_y, resizable=True, on_resize=self.on_clock_resize, save_callback=self.save_global_layout)
        self.root = self.clock_mod.win 
        self.clock_canvas = tk.Canvas(self.root, bg=self.bg_color, bd=0, highlightthickness=0)
        self.clock_canvas.pack(fill=tk.BOTH, expand=True)
        self.clock_mod.setup_bindings(self.clock_canvas)

        # Art cover window
        self.art_mod = DraggableModule("art_layer", 60, 60, start_x + 145, start_y, resizable=True, on_resize=self.on_art_resize, save_callback=self.save_global_layout)
        self.art_border = tk.Frame(self.art_mod.win, bg="black", bd=2)
        self.art_border.pack(fill=tk.BOTH, expand=True)
        self.art_label = tk.Label(self.art_border, bg=self.bg_color, bd=0, highlightthickness=0)
        self.art_label.pack(fill=tk.BOTH, expand=True)
        self.art_mod.setup_bindings(self.art_label)
        self.load_default_art()

        # Track data window
        self.info_mod = DraggableModule("info_layer", 300, 60, start_x + 220, start_y, resizable=True, on_resize=self.on_info_resize, save_callback=self.save_global_layout)
        self.info_canvas = tk.Canvas(self.info_mod.win, bg=self.bg_color, bd=0, highlightthickness=0)
        self.info_canvas.pack(fill=tk.BOTH, expand=True)
        self.track_text = "> syncing feeds..."
        self.artist_text = "  waiting for stream"
        self.info_mod.setup_bindings(self.info_canvas)

        # soundwave window
        self.viz_mod = DraggableModule("viz_layer", 140, 60, start_x + 535, start_y, resizable=False, save_callback=self.save_global_layout)
        self.viz_canvas = tk.Canvas(self.viz_mod.win, bg=self.bg_color, bd=0, highlightthickness=0)
        self.viz_canvas.pack(fill=tk.BOTH, expand=True)
        self.viz_mod.setup_bindings(self.viz_canvas)

        # Bootsrap view layoutsssssssssssssssss somet hing soemtihng
        self.update_clock()
        self.update_info_text()

        # pawn backend loops
        threading.Thread(target=self.start_async_media_loop, daemon=True).start()
        threading.Thread(target=self.audio_capture_stream, daemon=True).start()
        # threading.Thread(target=self.adapt_to_wallpaper, daemon=True).start() sorry mate, deprecated for gaming
        
        self.draw_visualizer_loop()
        self.root.mainloop()

    def on_clock_resize(self, w, h):
        self.update_clock()

    def on_art_resize(self, w, h):
        if hasattr(self, 'raw_art_img'):
            self.render_art_frame(self.raw_art_img)

    def on_info_resize(self, w, h):
        self.update_info_text()

    def save_global_layout(self):
        """Grabs active geometry states from all separate window nodes and flushes them to jsonion"""
        try:
            layout_data = {}
            modules = {
                "main": self.clock_mod,
                "art_layer": self.art_mod,
                "info_layer": self.info_mod,
                "viz_layer": self.viz_mod
            }
            
            for key, mod in modules.items():
                layout_data[key] = {
                    "x": mod.win.winfo_x(),
                    "y": mod.win.winfo_y(),
                    "w": mod.win.winfo_width(),
                    "h": mod.win.winfo_height()
                }
                
            with open("layout_settings.json", "w") as f:
                json.dump(layout_data, f, indent=4)
        except Exception: pass

    def update_clock(self):
        time_str = time.strftime("%I:%M %p")
        if time_str.startswith("0"): 
            time_str = time_str[1:]
        self.clock_text = f"[ {time_str} ]"
        
        self.clock_canvas.delete("all")
        h = self.clock_mod.win.winfo_height()
        x, y = 5, h // 2
        
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.clock_canvas.create_text(x+dx, y+dy, text=self.clock_text, font=("consolas", 14, "bold"), fill="black", anchor="w")
        self.clock_canvas.create_text(x, y, text=self.clock_text, font=("consolas", 14, "bold"), fill=self.accent_color, anchor="w")
        
        self.root.after(1000, self.update_clock)

    def update_info_text(self):
        self.info_canvas.delete("all")
        h = self.info_mod.win.winfo_height()
        
        t_x, t_y = 0, int(h * 0.3)
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.info_canvas.create_text(t_x+dx, t_y+dy, text=self.track_text, font=("consolas", 12, "bold"), fill="black", anchor="w")
        self.info_canvas.create_text(t_x, t_y, text=self.track_text, font=("consolas", 12, "bold"), fill=self.accent_color, anchor="w")
        
        a_x, a_y = 0, int(h * 0.7)
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (-2,0), (2,0), (0,-2), (0,2)]:
            self.info_canvas.create_text(a_x+dx, a_y+dy, text=self.artist_text, font=("consolas", 9), fill="black", anchor="w")
        self.info_canvas.create_text(a_x, a_y, text=self.artist_text, font=("consolas", 9), fill=self.sub_color, anchor="w")

    def load_default_art(self):
        self.raw_art_img = Image.new('RGB', (100, 100), color='#0a0a0a')
        self.render_art_frame(self.raw_art_img)

    def render_art_frame(self, pil_img):
        self.raw_art_img = pil_img
        w = max(10, self.art_mod.win.winfo_width() - 4)
        h = max(10, self.art_mod.win.winfo_height() - 4)
        resized = pil_img.resize((w, h), Image.Resampling.LANCZOS)
        self.photo_art = ImageTk.PhotoImage(resized)
        self.art_label.config(image=self.photo_art)

    def fetch_album_art_metadata(self, track_name):
        try:
            query = urllib.parse.quote(track_name)
            url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
            # Uses itunes cuz spotify fucking locke down api
            req = urllib.request.Request(url, headers={'user-agent': 'mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if data['results']:
                    # Full 600x600 high-res asset instead of 100x100 thumbnail
                    img_url = data['results'][0]['artworkUrl60'].replace('60x60bb', '600x600bb')
                    with urllib.request.urlopen(img_url) as img_res:
                        return Image.open(img_res)
        except Exception: pass
        return None

    def start_async_media_loop(self):
        asyncio.run(self.track_media_via_smtc())

    async def track_media_via_smtc(self):
        while True:
            try:
                manager = await SessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    info = await session.try_get_media_properties_async()
                    if info:
                        song = info.title 
                        artist = info.artist
                        combo = f"{song} - {artist}"
                        
                        if combo != self.current_song:
                            self.current_song = combo
                            self.track_text = f"> {song}" if len(song) < 24 else f"> {song[:21]}..."
                            self.artist_text = f"  {artist}" if len(artist) < 28 else f"  {artist[:25]}..."
                            
                            self.root.after(0, self.update_info_text)
                            threading.Thread(target=self.apply_artwork_thread, args=(song,), daemon=True).start()
            except Exception: pass
            await asyncio.sleep(0.6)

    def apply_artwork_thread(self, search_term):
        art_img = self.fetch_album_art_metadata(search_term)
        if art_img:
            self.render_art_frame(art_img)
        else:
            self.load_default_art()

    def audio_capture_stream(self):
        target_device = 16 

        def audio_callback(indata, frames, time, status):
            if status and 'input overflow' not in str(status).lower():
                return
            
            peak_val = np.max(np.abs(indata)) * 100
            
            if peak_val > 0.15:
                self.audio_active = True
                if peak_val > self.max_seen:
                    self.max_seen = peak_val
                else:
                    self.max_seen = max(0.5, self.max_seen * 0.98) 
                
                max_h = max(10, self.viz_mod.win.winfo_height() - 5)
                base_height = (peak_val / self.max_seen) * max_h
                
                new_bars = []
                for i in range(self.num_bars):
                    wave_modifier = np.random.uniform(0.4, 1.1)
                    val = min(base_height * wave_modifier, max_h)
                    new_bars.append(val)
                
                self.bar_data = [max(old * 0.3, new) for old, new in zip(self.bar_data, new_bars)]
            else:
                self.audio_active = False

        try:
            with sd.InputStream(callback=audio_callback, channels=2, blocksize=1024, device=target_device):
                while True: time.sleep(1)
        except Exception:
            while True: time.sleep(1)

    def draw_visualizer_loop(self):
        self.viz_canvas.delete("all")
        w = self.viz_mod.win.winfo_width()
        h = self.viz_mod.win.winfo_height()
        bar_width = w / self.num_bars

        for i in range(self.num_bars):
            val = self.bar_data[i]
            val = max(val, 4) 
            
            x_center = i * bar_width + (bar_width / 2)
            y_bottom = h - 2
            y_top = h - val
            
            self.viz_canvas.create_line(x_center, y_bottom, x_center, y_top, fill='black', width=max(1, bar_width - 1), capstyle="round")
            self.viz_canvas.create_line(x_center, y_bottom, x_center, y_top, fill='white', width=max(1, bar_width - 5), capstyle="round")
            
        if not self.audio_active:
            self.bar_data = [max(x - 5, 0) for x in self.bar_data]
            
        self.root.after(16, self.draw_visualizer_loop)

    # def adapt_to_wallpaper(self):
    #     while True:
    #         try:
    #             x, y = self.info_mod.win.winfo_x(), self.info_mod.win.winfo_y()
    #             w, h = self.info_mod.win.winfo_width(), self.info_mod.win.winfo_height()
    #             img = ImageGrab.grab((x, y, x + w, y + h))
    #             brightness = ImageStat.Stat(img.convert('L')).mean[0]
                
    #             self.accent_color = "black" if brightness > 127 else "white"
    #             self.sub_color = "#333333" if brightness > 127 else "gray"
                
    #             self.root.after(0, lambda: [self.update_clock(), self.update_info_text()])
    #         except Exception: pass
    #         time.sleep(1.5)

if __name__ == "__main__":
    CoolAssDecoShit()
