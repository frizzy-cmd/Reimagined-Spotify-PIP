# Reimagined Spotify PIP [Reimagined SPIP]
**A simple Spotify overlay with tkinter (yes, you heard that right tkinter) that diplays what you are listening to, artist name, song name, artwork cover, time, soundwaves, etc into one beautiful and compact errr space. idk im just typing anything**

**You can also hold left click to drag the elements, or drag right click to resize. Resizing of the soundwaves is locked to keep stuff stable.**

## ⚠️ Scroll down to the bottom for general help, If you are experiencing problems then that problem is probably in there.

---

# Requirements to get this application:
- **Python 3.x** installed
- A **stereo mix or virtual audio loopback device** enabled in your sound settings [Fancy term for make sure you have a speaker]

# Libraries to get this application:
```
pip install sounddevice numpy pywin32 pillow winrt-windows.media.control
```
# Installation
Clone this repository or just grab the standalone .py file, then open your terminal in the project directory and run the command to get all required libraries.

---

## ⚠️ General problems
Problem: Help! I wanna reset back to the default position but i dont know how to!
- Delete the ```reimaginedpip.json``` file on your Desktop, then relaunch the app.

Problem: How do I close the app? 
- Just Ctrl + C in your terminal, or open Task Manager and end the ```main``` process.

Problem: I want the app to start on startup
- Too lazy go edit the py manually

Problem: The cover art on the PIP is different than the Spotify one
- This is a nice question, The album art gets fetched from iTunes instead of Spotify, due to Spotify's greed locking down the API to premium users only. Some covers remain the same and most covers aren't, Take it or leave it


**P/S: This is just a fun little project I made for myself and not intended for public use, but why not share it to everyone else?**

