"""
GeoFlowAI — Agent 4 Debugger/Runner GUI
Iron-Man / HUD aesthetic (Emerald/Matrix Green Accent)
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
BG           = "#030d03"
BG_PANEL     = "#061406" 
EMERALD      = "#00ff7f"
MATRIX       = "#00ff41" # Matrix green
GLOW         = "#b9ffb9"
DIM_GREEN    = "#003b00"
RED          = "#ff3333"
WHITE        = "#e0f0e0"
GREY         = "#2b3b2b"
DARK_GREY    = "#0a130a"

class HUDFrame(tk.Frame):
    def __init__(self, master, highlight=DIM_GREEN, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("highlightbackground", highlight)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 10)
        super().__init__(master, **kw)

class DiagnosticSpinner(tk.Canvas):
    """Animated 'diagnostic radar' spinner for Agent 4."""
    def __init__(self, master, size=120, **kw):
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

        # Radar sweep
        self.create_arc(cx-50, cy-50, cx+50, cy+50, start=self.angle, extent=60, 
                        fill=DIM_GREEN, outline="", tags="spinner")
        
        # Grid lines
        self.create_oval(cx-50, cy-50, cx+50, cy+50, outline=DIM_GREEN, width=1, tags="spinner")
        self.create_oval(cx-30, cy-30, cx+30, cy+30, outline=DIM_GREEN, width=1, tags="spinner")
        self.create_line(cx-55, cy, cx+55, cy, fill=DIM_GREEN, tags="spinner")
        self.create_line(cx, cy-55, cx, cy+55, fill=DIM_GREEN, tags="spinner")

        # Sweeper lead line
        a = math.radians(self.angle + 60)
        lx = cx + math.cos(a) * 50
        ly = cy - math.sin(a) * 50
        self.create_line(cx, cy, lx, ly, fill=MATRIX, width=2, tags="spinner")

    def start(self):
        self.running = True
        self._tick()

    def stop(self):
        self.running = False
        self.delete("spinner")

    def _tick(self):
        if not self.running: return
        self.angle = (self.angle - 10) % 360
        self._draw()
        self.after(40, self._tick)

class DiagnosticTerminal(tk.Text):
    """Scrolling terminal with category highlighting."""
    def __init__(self, master, **kw):
        kw.setdefault("bg", "#020802")
        kw.setdefault("fg", MATRIX)
        kw.setdefault("insertbackground", MATRIX)
        kw.setdefault("relief", "flat")
        kw.setdefault("padx", 10)
        kw.setdefault("pady", 10)
        kw.setdefault("state", "disabled")
        kw.setdefault("font", ("Consolas", 10))
        super().__init__(master, **kw)
        
        # Tags for categories
        self.tag_configure("info", foreground=MATRIX)
        self.tag_configure("sync", foreground=EMERALD)
        self.tag_configure("sync-ok", foreground=DIM_GREEN)
        self.tag_configure("exec", foreground=GLOW, font=("Consolas", 10, "bold"))
        self.tag_configure("success", foreground=EMERALD, font=("Consolas", 10, "bold"))
        self.tag_configure("error", foreground=RED, font=("Consolas", 10, "bold"))
        self.tag_configure("debug", foreground="#ffea00") # Yellow
        self.tag_configure("debug-fix", foreground="#00d4ff") # Cyan
        self.tag_configure("stdout", foreground=WHITE)
        self.tag_configure("stderr", foreground="#ff7777")
        self.tag_configure("warning", foreground="#ffa500")

    def log(self, text, category="info"):
        self.configure(state="normal")
        timestamp = time.strftime("[%H:%M:%S] ")
        self.insert("end", timestamp, "info")
        self.insert("end", f"{text}\n", category)
        self.see("end")
        self.configure(state="disabled")

class Agent4Window:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G E O F L O W  A I  ·  A G E N T  4  ·  D E B U G G E R  &  R U N N E R")
        self.root.configure(bg=BG)
        self.root.geometry("1200x850")
        
        self.font_title  = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.font_sub    = tkfont.Font(family="Consolas", size=10)
        self.font_btn    = tkfont.Font(family="Consolas", size=10, weight="bold")

        self._build_ui()
        self._load_workflow()
        self._is_running = False

    def _build_ui(self):
        # ── Top bar ──
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(top, text="◈  GEOFLOW AI", font=self.font_title, fg=MATRIX, bg=BG).pack(side="left")
        tk.Label(top, text="AGENT 4 · DIAGNOSTIC RUNNER & DEBUGGER", font=self.font_sub, fg=EMERALD, bg=BG).pack(side="right")

        # ── Status ──
        self.status_bar = tk.Frame(self.root, bg=BG)
        self.status_bar.pack(fill="x", padx=20)
        self.status_label = tk.Label(self.status_bar, text="SYSTEM INITIALIZED", font=self.font_sub, fg=DIM_GREEN, bg=BG)
        self.status_label.pack(side="left")

        # ── Center Area ──
        center = tk.Frame(self.root, bg=BG)
        center.pack(fill="both", expand=True, padx=20, pady=10)

        # Left: Pipeline Steps
        left_panel = HUDFrame(center, width=320)
        left_panel.pack_propagate(False)
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 10))
        tk.Label(left_panel, text="▸ EXECUTION PIPELINE", font=self.font_sub, fg=MATRIX, bg=BG_PANEL).pack(anchor="w")
        
        self.step_tree = ttk.Treeview(left_panel, selectmode="browse", show="tree", height=20)
        self.step_tree.pack(fill="both", expand=True, pady=(10, 0))
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=DARK_GREY, foreground=WHITE, fieldbackground=DARK_GREY, borderwidth=0)
        style.map("Treeview", background=[('selected', DIM_GREEN)])

        # Right: Real-time Diagnostics
        right_panel = HUDFrame(center)
        right_panel.pack(side="right", fill="both", expand=True)
        
        header = tk.Frame(right_panel, bg=BG_PANEL)
        header.pack(fill="x")
        tk.Label(header, text="▸ SYSTEM DIAGNOSTICS", font=self.font_sub, fg=MATRIX, bg=BG_PANEL).pack(side="left")
        
        self.diag_term = DiagnosticTerminal(right_panel)
        self.diag_term.pack(fill="both", expand=True, pady=(10, 0))

        # Radar Overlay (placed when running)
        self.radar_frame = tk.Frame(self.diag_term, bg="#020802")
        self.radar = DiagnosticSpinner(self.radar_frame, bg="#020802")
        self.radar.pack()
        tk.Label(self.radar_frame, text="SCANNING PIPELINE…", font=self.font_sub, fg=MATRIX, bg="#020802").pack()

        # ── Bottom Action ──
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_run_all = tk.Button(bottom, text="⚡ EXECUTE FULL PIPELINE", font=self.font_btn, 
                                    bg=DIM_GREEN, fg=WHITE, relief="flat", padx=25, pady=10,
                                    command=self._on_run_all)
        self.btn_run_all.pack(side="right")

        self.btn_run_step = tk.Button(bottom, text="▸ EXECUTE SELECTED", font=self.font_btn, 
                                     bg=GREY, fg=WHITE, relief="flat", padx=15, pady=10,
                                     command=self._on_run_step)
        self.btn_run_step.pack(side="right", padx=10)

    def _load_workflow(self):
        path = os.path.join(config.OUTPUT_DIR, "workflow_plan.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                self.workflow_data = json.load(f)
            for step in self.workflow_data:
                self.step_tree.insert("", "end", iid=step['step_id'], text=f" {step['step_id']} · {step['algorithm']}")
            self.diag_term.log(f"LOADED WORKFLOW: {len(self.workflow_data)} NODES DETECTED", "success")
        else:
            self.diag_term.log("CRITICAL: workflow_plan.json NOT FOUND", "error")

    def _on_run_all(self):
        if self._is_running: return
        self._is_running = True
        self.btn_run_all.configure(state="disabled", bg=GREY)
        self.radar_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.radar.start()
        
        threading.Thread(target=self._full_pipeline_thread, daemon=True).start()

    def _on_run_step(self):
        sel = self.step_tree.selection()
        if not sel: return
        step_id = sel[0]
        step_data = next((s for s in self.workflow_data if s['step_id'] == step_id), None)
        if step_data:
            threading.Thread(target=self._single_step_thread, args=(step_data,), daemon=True).start()

    def _full_pipeline_thread(self):
        try:
            from agent4_run_debug import Agent4Debugger
            self.debugger = Agent4Debugger(log_callback=self._gui_log)
            
            for step in self.workflow_data:
                self.root.after(0, lambda s=step['step_id']: self._highlight_step(s))
                
                script_path = os.path.join(config.OUTPUT_DIR, step['script_filename'])
                success = self.debugger.run_step(
                    script_path, 
                    input_files=step['input_files'], 
                    output_file=step['output_file']
                )
                
                if not success:
                    self._gui_log(f"PIPELINE CRITICAL FAILURE AT {step['step_id']}", "critical")
                    break
            
            self.root.after(0, self._on_pipeline_finished)
        except Exception as e:
            self._gui_log(f"CORE ENGINE ERROR: {e}", "critical")
            self.root.after(0, self._on_pipeline_finished)

    def _single_step_thread(self, step):
        from agent4_run_debug import Agent4Debugger
        db = Agent4Debugger(log_callback=self._gui_log)
        script_path = os.path.join(config.OUTPUT_DIR, step['script_filename'])
        db.run_step(script_path, input_files=step['input_files'], output_file=step['output_file'])

    def _highlight_step(self, step_id):
        self.step_tree.selection_set(step_id)
        self.step_tree.see(step_id)

    def _gui_log(self, msg, cat):
        self.root.after(0, lambda: self.diag_term.log(msg, cat))

    def _on_pipeline_finished(self):
        self._is_running = False
        self.radar.stop()
        self.radar_frame.place_forget()
        self.btn_run_all.configure(state="normal", bg=DIM_GREEN)
        self.diag_term.log("PIPELINE EXECUTION PHASE CONCLUDED", "success")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = Agent4Window()
    app.run()