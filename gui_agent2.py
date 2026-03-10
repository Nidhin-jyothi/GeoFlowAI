"""
GeoFlowAI — Agent 2 Schematizer GUI
Iron-Man / HUD aesthetic (Amber Accent)
Uses only tkinter (no extra GUI dependencies).
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import threading
import json
import os
import math
import time
import config

# ── Colour Palette ──────────────────────────────────────────────
BG           = "#0a0e17"
BG_PANEL     = "#0d1320"
AMBER        = "#ff9f1c"
AMBER_DIM    = "#7a4c0e"
AMBER_GLOW   = "#ffb347"
CYAN         = "#00d4ff"
CYAN_DIM     = "#006680"
RED          = "#ff3d3d"
WHITE        = "#e0e6ed"
GREY         = "#3a4556"
DARK_GREY    = "#1a2233"

# ── Arc-Reactor spinner parameters (Amber version) ──────────────
ARC_SIZE     = 100
ARC_R_OUTER  = 40
ARC_R_INNER  = 25
ARC_SPEED    = 5

class HUDFrame(tk.Frame):
    """Utility: a frame with a thin amber border to look like a HUD panel."""
    def __init__(self, master, highlight=AMBER_DIM, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("highlightbackground", highlight)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 10)
        super().__init__(master, **kw)

class DataStreamSpinner(tk.Canvas):
    """Animated data stream spinner for Agent 2."""
    def __init__(self, master, size=ARC_SIZE, **kw):
        kw.setdefault("bg", BG)
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, width=size, height=size, **kw)
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.angle = 0
        self.running = False

    def _draw(self):
        self.delete("spinner")
        cx, cy = self.cx, self.cy

        # Rotating hexagon bits
        for i in range(6):
            a = math.radians(self.angle + i * 60)
            x1 = cx + math.cos(a) * ARC_R_OUTER
            y1 = cy + math.sin(a) * ARC_R_OUTER
            x2 = cx + math.cos(a + 0.5) * ARC_R_INNER
            y2 = cy + math.sin(a + 0.5) * ARC_R_INNER
            self.create_line(x1, y1, x2, y2, fill=AMBER, width=2, tags="spinner")

        # Inner pulsing circle
        pulse = (math.sin(self.angle * 0.1) + 1) * 5 + 10
        self.create_oval(cx-pulse, cy-pulse, cx+pulse, cy+pulse, 
                         outline=AMBER_GLOW, width=1, tags="spinner")

    def start(self):
        self.running = True
        self._tick()

    def stop(self):
        self.running = False
        self.delete("spinner")

    def _tick(self):
        if not self.running:
            return
        self.angle = (self.angle + ARC_SPEED) % 360
        self._draw()
        self.after(30, self._tick)

class JSONTypewriter(tk.Text):
    """Typewriter text widget optimized for JSON code blocks."""
    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("fg", WHITE)
        kw.setdefault("insertbackground", AMBER)
        kw.setdefault("relief", "flat")
        kw.setdefault("wrap", "none")
        kw.setdefault("padx", 15)
        kw.setdefault("pady", 15)
        kw.setdefault("state", "disabled")
        kw.setdefault("highlightbackground", AMBER_DIM)
        kw.setdefault("highlightthickness", 1)
        super().__init__(master, **kw)
        
        self.tag_configure("key", foreground=AMBER_GLOW)
        self.tag_configure("string", foreground=CYAN)
        self.tag_configure("number", foreground="#fd79a8") # Pinkish
        self.tag_configure("bracket", foreground=WHITE)

    def typewrite(self, text, speed=15):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self._queue = text
        self._idx = 0
        self._speed = speed
        self._typing = True
        self._tick()

    def _tick(self):
        if not self._typing:
            return
        end = min(self._idx + self._speed, len(self._queue))
        chunk = self._queue[self._idx:end]
        self.insert("end", chunk)
        self.see("end")
        self._idx = end
        if self._idx >= len(self._queue):
            self._typing = False
            self.configure(state="disabled")
            self._syntax_highlight()
            return
        self.after(20, self._tick)

    def _syntax_highlight(self):
        """Simple regex-less syntax highlighting for JSON."""
        self.configure(state="normal")
        content = self.get("1.0", "end")
        
        # Keys (inside quotes before colon)
        import re
        for match in re.finditer(r'"[^"]*"\s*:', content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end() - 1} chars"
            self.tag_add("key", start, end)
            
        # Strings (inside quotes not followed by colon)
        for match in re.finditer(r':\s*"[^"]*"', content):
            start = f"1.0 + {match.start() + match.group().find('\"')} chars"
            end = f"1.0 + {match.end()} chars"
            self.tag_add("string", start, end)

        self.configure(state="disabled")

class Agent2Window:
    """Main GUI window for Agent 2 — the Schematizer."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G E O F L O W  A I  ·  A G E N T  2  ·  S C H E M A T I Z E R")
        self.root.configure(bg=BG)
        self.root.geometry("1000x750")
        
        self.font_title  = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.font_sub    = tkfont.Font(family="Consolas", size=10)
        self.font_btn    = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.font_output = tkfont.Font(family="Consolas", size=10)

        self._build_ui()

    def _build_ui(self):
        # ── Top bar ──
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(top, text="◈  GEOFLOW AI", font=self.font_title, fg=AMBER, bg=BG).pack(side="left")
        tk.Label(top, text="AGENT 2 · WORKFLOW SCHEMATIZER", font=self.font_sub, fg=CYAN, bg=BG).pack(side="right")

        # ── Status ──
        self.status_bar = tk.Frame(self.root, bg=BG)
        self.status_bar.pack(fill="x", padx=20)
        self.status_label = tk.Label(self.status_bar, text="SYSTEM READY", font=self.font_sub, fg=GREY, bg=BG)
        self.status_label.pack(side="left")

        # ── Center Area ──
        center = tk.Frame(self.root, bg=BG)
        center.pack(fill="both", expand=True, padx=20, pady=10)

        # Left: Plan Input View
        left_panel = HUDFrame(center)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left_panel, text="▸ SOURCE PLAN", font=self.font_sub, fg=AMBER, bg=BG_PANEL).pack(anchor="w")
        self.plan_view = tk.Text(left_panel, bg=BG_PANEL, fg=GREY, font=self.font_output, 
                                 relief="flat", wrap="word", borderwidth=0)
        self.plan_view.pack(fill="both", expand=True, pady=(10, 0))
        self._load_source_plan()

        # Right: JSON Schema View
        right_panel = HUDFrame(center)
        right_panel.pack(side="right", fill="both", expand=True)
        tk.Label(right_panel, text="▸ EXECUTION SCHEMA (JSON)", font=self.font_sub, fg=AMBER, bg=BG_PANEL).pack(anchor="w")
        
        self.json_view = JSONTypewriter(right_panel, font=self.font_output)
        self.json_view.pack(fill="both", expand=True, pady=(10, 0))

        # Spinner (Overlay-ish)
        self.spinner_frame = tk.Frame(right_panel, bg=BG_PANEL)
        self.spinner = DataStreamSpinner(self.spinner_frame, bg=BG_PANEL)
        self.spinner.pack()
        tk.Label(self.spinner_frame, text="STRUCTURING DATA…", font=self.font_sub, fg=AMBER, bg=BG_PANEL).pack()

        # ── Action Bar ──
        action_bar = tk.Frame(self.root, bg=BG)
        action_bar.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_structure = tk.Button(action_bar, text="⚡ GENERATE SCHEMA", font=self.font_btn, 
                                      bg=AMBER_DIM, fg=WHITE, relief="flat", padx=20, pady=8,
                                      command=self._on_structure)
        self.btn_structure.pack(side="right")

        self.btn_save = tk.Button(action_bar, text="💾 SAVE WORKFLOW", font=self.font_btn, 
                                 bg=DARK_GREY, fg=GREY, relief="flat", padx=15, pady=8,
                                 state="disabled", command=self._on_save)
        self.btn_save.pack(side="right", padx=10)

    def _load_source_plan(self):
        plan_path = os.path.join(config.OUTPUT_DIR, "step1_plan.txt")
        if os.path.exists(plan_path):
            with open(plan_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.plan_view.insert("1.0", content)
            self.status_label.configure(text="PLAN LOADED")
        else:
            self.plan_view.insert("1.0", "⚠️ No plan found in outputs/step1_plan.txt")

    def _on_structure(self):
        plan_text = self.plan_view.get("1.0", "end").strip()
        if not plan_text: return

        self.btn_structure.configure(state="disabled", bg=DARK_GREY)
        self.spinner_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.spinner.start()
        self.status_label.configure(text="AGENT 2 IS REASONING…", fg=AMBER)

        threading.Thread(target=self._run_schematizer, args=(plan_text,), daemon=True).start()

    def _run_schematizer(self, text):
        try:
            from agent2_schematizer import Agent2Schematizer
            schematizer = Agent2Schematizer()
            steps = schematizer.structure_plan(text)
            self._schema_data = {"steps": steps}
            json_str = json.dumps(self._schema_data, indent=2)
            self.root.after(0, lambda: self._on_ready(json_str))
        except Exception as e:
            self.root.after(0, lambda: self._on_error(str(e)))

    def _on_ready(self, json_str):
        self.spinner.stop()
        self.spinner_frame.place_forget()
        self.json_view.typewrite(json_str)
        self.btn_structure.configure(state="normal", bg=AMBER_DIM)
        self.btn_save.configure(state="normal", bg=CYAN_DIM, fg=WHITE)
        self.status_label.configure(text="SCHEMA GENERATED", fg=CYAN)

    def _on_error(self, err):
        self.spinner.stop()
        self.spinner_frame.place_forget()
        self.status_label.configure(text=f"ERROR: {err[:50]}", fg=RED)
        self.btn_structure.configure(state="normal", bg=AMBER_DIM)

    def _on_save(self):
        if not hasattr(self, "_schema_data"): return
        path = os.path.join(config.OUTPUT_DIR, "workflow_plan.json")
        with open(path, "w") as f:
            json.dump(self._schema_data["steps"], f, indent=2)
        self.status_label.configure(text=f"WORKFLOW SAVED → {path}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = Agent2Window()
    app.run()
