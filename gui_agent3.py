"""
GeoFlowAI — Agent 3 Code Generator GUI (v2)
Unified Generate → Execute → Debug pipeline per step.
Iron-Man / HUD aesthetic (Purple/Magenta Accent)
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
BG_PANEL     = "#120a17"
PURPLE       = "#bc13fe"
PURPLE_DIM   = "#4a0072"
PURPLE_GLOW  = "#e0aaff"
CYAN         = "#00d4ff"
AMBER        = "#ff9f1c"
WHITE        = "#e0e6ed"
GREY         = "#3a4556"
DARK_GREY    = "#1a1520"
RED          = "#ff3d3d"
GREEN        = "#00ff7f"

# ── Step status colors ───────────────────────────────────────────
STATUS_COLORS = {
    "pending":    GREY,
    "generating": AMBER,
    "running":    CYAN,
    "success":    GREEN,
    "failed":     RED,
    "debugging":  PURPLE_GLOW,
}

ARC_SIZE = 100
ARC_SPEED = 6

class HUDFrame(tk.Frame):
    def __init__(self, master, highlight=PURPLE_DIM, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("highlightbackground", highlight)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 10)
        super().__init__(master, **kw)

class CodeParticleSpinner(tk.Canvas):
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
        for i in range(3):
            r = 20 + i * 8
            a = math.radians(self.angle * (1 + i * 0.5))
            x = cx + math.cos(a) * r
            y = cy + math.sin(a) * r
            self.create_oval(x-2, y-2, x+2, y+2, fill=PURPLE_GLOW, outline=PURPLE, tags="spinner")
            self.create_arc(cx-r, cy-r, cx+r, cy+r, start=math.degrees(-a)-40, extent=40,
                            outline=PURPLE_DIM, style="arc", tags="spinner")

    def start(self):
        self.running = True
        self._tick()

    def stop(self):
        self.running = False
        self.delete("spinner")

    def _tick(self):
        if not self.running: return
        self.angle = (self.angle + ARC_SPEED) % 360
        self._draw()
        self.after(30, self._tick)

class PipelineTerminal(tk.Text):
    """Scrolling log view for pipeline activity."""
    def __init__(self, master, **kw):
        kw.setdefault("bg", "#0b0014")
        kw.setdefault("fg", WHITE)
        kw.setdefault("insertbackground", PURPLE)
        kw.setdefault("relief", "flat")
        kw.setdefault("padx", 10)
        kw.setdefault("pady", 10)
        kw.setdefault("state", "disabled")
        kw.setdefault("font", ("Consolas", 10))
        kw.setdefault("wrap", "word")
        super().__init__(master, **kw)

        self.tag_configure("info",       foreground=WHITE)
        self.tag_configure("generate",   foreground=AMBER,      font=("Consolas", 10, "bold"))
        self.tag_configure("run",        foreground=CYAN,       font=("Consolas", 10, "bold"))
        self.tag_configure("success",    foreground=GREEN,      font=("Consolas", 10, "bold"))
        self.tag_configure("error",      foreground=RED,        font=("Consolas", 10, "bold"))
        self.tag_configure("debug",      foreground=PURPLE_GLOW)
        self.tag_configure("code",       foreground=GREY)
        self.tag_configure("step",       foreground=PURPLE,     font=("Consolas", 10, "bold"))

    def log(self, text, tag="info"):
        self.configure(state="normal")
        ts = time.strftime("[%H:%M:%S] ")
        self.insert("end", ts, "info")
        self.insert("end", f"{text}\n", tag)
        self.see("end")
        self.configure(state="disabled")

class Agent3Window:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G E O F L O W  A I  ·  A G E N T  3  ·  C O D E  G E N  +  E X E C U T E")
        self.root.configure(bg=BG)
        self.root.geometry("1200x850")

        self.font_title = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.font_sub   = tkfont.Font(family="Consolas", size=10)
        self.font_btn   = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.font_code  = tkfont.Font(family="Consolas", size=10)

        self.workflow_data = []
        self.step_status   = {}  # step_id → status string
        self._is_running   = False

        self._build_ui()
        self._load_workflow()

    def _build_ui(self):
        # ── Top bar
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(top, text="◈  GEOFLOW AI", font=self.font_title, fg=PURPLE, bg=BG).pack(side="left")
        tk.Label(top, text="AGENT 3 · SYNTHESIZE  →  EXECUTE  →  VERIFY", font=self.font_sub, fg=CYAN, bg=BG).pack(side="right")

        # ── Status bar
        self.status_bar = tk.Frame(self.root, bg=BG)
        self.status_bar.pack(fill="x", padx=20)
        self.status_label = tk.Label(self.status_bar, text="AWAITING DIRECTIVE", font=self.font_sub, fg=GREY, bg=BG)
        self.status_label.pack(side="left")

        # ── Center area
        center = tk.Frame(self.root, bg=BG)
        center.pack(fill="both", expand=True, padx=20, pady=10)

        # ── LEFT: Step pipeline list
        left_panel = HUDFrame(center, width=320)
        left_panel.pack_propagate(False)
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 10))

        tk.Label(left_panel, text="▸ PIPELINE STEPS", font=self.font_sub, fg=PURPLE, bg=BG_PANEL).pack(anchor="w")

        self.step_list = tk.Listbox(left_panel, bg=DARK_GREY, fg=WHITE, font=self.font_sub,
                                    borderwidth=0, highlightthickness=0,
                                    selectbackground=PURPLE_DIM, activestyle="none")
        self.step_list.pack(fill="both", expand=True, pady=(10, 0))

        # ── RIGHT: Tabs — Code view + Log
        right_panel = HUDFrame(center)
        right_panel.pack(side="right", fill="both", expand=True)

        nb_style = ttk.Style()
        nb_style.theme_use("clam")
        nb_style.configure("TNotebook", background=BG_PANEL, borderwidth=0)
        nb_style.configure("TNotebook.Tab", background=DARK_GREY, foreground=GREY,
                           font=("Consolas", 10), padding=(8, 4))
        nb_style.map("TNotebook.Tab", background=[("selected", PURPLE_DIM)],
                     foreground=[("selected", WHITE)])

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill="both", expand=True)

        # Code tab
        code_tab = tk.Frame(self.notebook, bg=BG_PANEL)
        self.notebook.add(code_tab, text=" ▸ GENERATED SCRIPT ")

        self.code_view = tk.Text(code_tab, bg="#0f0814", fg=PURPLE_GLOW, font=self.font_code,
                                 relief="flat", wrap="none", padx=12, pady=12,
                                 state="disabled", insertbackground=PURPLE,
                                 highlightthickness=0)
        code_scroll = ttk.Scrollbar(code_tab, command=self.code_view.yview)
        self.code_view.configure(yscrollcommand=code_scroll.set)
        code_scroll.pack(side="right", fill="y")
        self.code_view.pack(fill="both", expand=True)

        # Log tab
        log_tab = tk.Frame(self.notebook, bg=BG_PANEL)
        self.notebook.add(log_tab, text=" ▸ EXECUTION LOG ")

        self.log_term = PipelineTerminal(log_tab)
        log_scroll = ttk.Scrollbar(log_tab, command=self.log_term.yview)
        self.log_term.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_term.pack(fill="both", expand=True)

        # Spinner overlay
        self.spinner_frame = tk.Frame(self.root, bg=BG)
        self.spinner = CodeParticleSpinner(self.spinner_frame, bg=BG)
        self.spinner.pack()
        self.spinner_lbl = tk.Label(self.spinner_frame, text="", font=self.font_sub, fg=PURPLE, bg=BG)
        self.spinner_lbl.pack()

        # ── Bottom actions
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_run = tk.Button(bottom, text="⚡ START PIPELINE", font=self.font_btn,
                                 bg=PURPLE_DIM, fg=WHITE, relief="flat", padx=20, pady=8,
                                 command=self._on_start_pipeline)
        self.btn_run.pack(side="right")

        self.btn_resume = tk.Button(bottom, text="▸ RESUME FROM SELECTED", font=self.font_btn,
                                    bg=DARK_GREY, fg=WHITE, relief="flat", padx=15, pady=8,
                                    command=self._on_resume_from)
        self.btn_resume.pack(side="right", padx=10)

    def _load_workflow(self):
        path = os.path.join(config.OUTPUT_DIR, "workflow_plan.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                self.workflow_data = json.load(f)
            for step in self.workflow_data:
                sid = step["step_id"]
                self.step_status[sid] = "pending"
                algo = step.get("algorithm_id") or step.get("algorithm", "unknown")
                self.step_list.insert("end", f"  ○  {sid}  ·  {algo}")
                self._color_row(sid, "pending")
            self.status_label.configure(
                text=f"WORKFLOW LOADED: {len(self.workflow_data)} STEPS", fg=CYAN)
            self.log_term.log(f"Loaded {len(self.workflow_data)}-step workflow.", "info")
        else:
            self.status_label.configure(text="⚠️ NO WORKFLOW JSON FOUND", fg=RED)

    def _color_row(self, step_id, status):
        """Update the list row icon and colour for a step."""
        idx = next((i for i, s in enumerate(self.workflow_data) if s["step_id"] == step_id), None)
        if idx is None: return
        icons = {"pending": "○", "generating": "◎", "running": "▶",
                 "success": "✔", "failed": "✘", "debugging": "⚙"}
        icon = icons.get(status, "○")
        step = self.workflow_data[idx]
        self.step_list.delete(idx)
        algo = step.get("algorithm_id") or step.get("algorithm", "unknown")
        self.step_list.insert(idx, f"  {icon}  {step_id}  ·  {algo}")
        self.step_list.itemconfigure(idx, fg=STATUS_COLORS.get(status, WHITE))


    def _set_spinner(self, visible, text=""):
        if visible:
            self.spinner_lbl.configure(text=text)
            self.spinner_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.spinner.start()
        else:
            self.spinner.stop()
            self.spinner_frame.place_forget()

    def _show_code(self, code):
        self.code_view.configure(state="normal")
        self.code_view.delete("1.0", "end")
        self.code_view.insert("end", code)
        self.code_view.configure(state="disabled")
        self.notebook.select(0)

    def _on_start_pipeline(self):
        if self._is_running: return
        self._is_running = True
        self.btn_run.configure(state="disabled", bg=DARK_GREY)
        threading.Thread(target=self._pipeline_thread, args=(0,), daemon=True).start()

    def _on_resume_from(self):
        if self._is_running: return
        sel = self.step_list.curselection()
        start_idx = sel[0] if sel else 0
        self._is_running = True
        self.btn_run.configure(state="disabled", bg=DARK_GREY)
        threading.Thread(target=self._pipeline_thread, args=(start_idx,), daemon=True).start()

    def _pipeline_thread(self, start_idx):
        """
        Core loop: for each step → generate code → execute → verify.
        Only proceeds to next step on success. Stops on failure.
        """
        from agent3_codegen import Agent3CodeGen
        from agent4_run_debug import Agent4Debugger

        self.root.after(0, lambda: self.log_term.log("═" * 55, "step"))
        self.root.after(0, lambda: self.log_term.log("PIPELINE INITIATED", "step"))
        self.root.after(0, lambda: self.log_term.log("═" * 55, "step"))

        codegen   = Agent3CodeGen()
        debugger  = Agent4Debugger(log_callback=self._gui_log)

        # ─── PRE-FLIGHT: Validate all algorithm IDs ─────────────
        valid_algos = set()
        try:
            index_path = os.path.join(config.BASE_DIR, "all_alg_ids.txt")
            with open(index_path, "r") as f:
                valid_algos = {line.strip() for line in f if line.strip()}
        except Exception:
            pass

        if valid_algos:
            for step in self.workflow_data[start_idx:]:
                algo = step.get("algorithm_id") or step.get("algorithm", "")
                if algo and algo not in valid_algos:
                    self._gui_log(
                        f"⚠️  VALIDATION: '{algo}' in {step['step_id']} does NOT exist in QGIS!",
                        "error")

        for i, step in enumerate(self.workflow_data[start_idx:], start=start_idx):
            sid = step["step_id"]
            
            # Optional: Add small delay to avoid hitting Rate Limits (Gemini 429)
            if i > start_idx:
                time.sleep(5)

            # ─── PHASE 1: Generate ───────────────────────────────
            self.root.after(0, lambda s=sid: self._color_row(s, "generating"))
            self.root.after(0, lambda s=sid: self.status_label.configure(
                text=f"GENERATING {s}…", fg=AMBER))
            self._gui_log(f"[{sid}] Generating PyQGIS script…", "generate")
            self.root.after(0, lambda: self._set_spinner(True, "SYNTHESIZING SCRIPT…"))

            code = codegen.generate_code(step)

            if not code.strip():
                self._gui_log(f"[{sid}] Code generation returned empty. Stopping.", "error")
                self.root.after(0, lambda s=sid: self._color_row(s, "failed"))
                break

            # Save generated script
            script_name = step.get("script_filename", f"{sid}.py")
            script_path = os.path.join(config.OUTPUT_DIR, script_name)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
            self._gui_log(f"[{sid}] Script saved → {script_name}", "generate")
            self.root.after(0, lambda c=code: self._show_code(c))

            # ─── PHASE 2: Execute + Debug ────────────────────────
            self.root.after(0, lambda s=sid: self._color_row(s, "running"))
            self.root.after(0, lambda s=sid: self.status_label.configure(
                text=f"EXECUTING {s}…", fg=CYAN))
            self._gui_log(f"[{sid}] Starting execution…", "run")
            self.root.after(0, lambda: self._set_spinner(True, "EXECUTING SCRIPT…"))

            success = debugger.run_step(
                script_path,
                step_data=step,
                max_retries=3
            )
            self.root.after(0, lambda: self._set_spinner(False))

            if success:
                self.root.after(0, lambda s=sid: self._color_row(s, "success"))
                self._gui_log(f"[{sid}] ✔  STEP COMPLETE", "success")
            else:
                self.root.after(0, lambda s=sid: self._color_row(s, "failed"))
                self._gui_log(f"[{sid}] ✘  STEP FAILED — pipeline halted", "error")
                self.root.after(0, lambda: self.status_label.configure(
                    text=f"PIPELINE HALTED AT {sid}", fg=RED))
                break
        else:
            # All steps completed
            self.root.after(0, lambda: self.status_label.configure(
                text="ALL STEPS COMPLETE  ✔", fg=GREEN))
            self.root.after(0, lambda: self.log_term.log("═" * 55, "step"))
            self.root.after(0, lambda: self.log_term.log("PIPELINE COMPLETE", "success"))
            self.root.after(0, lambda: self.log_term.log("═" * 55, "step"))

        self.root.after(0, self._pipeline_finished)

    def _pipeline_finished(self):
        self._is_running = False
        self._set_spinner(False)
        self.btn_run.configure(state="normal", bg=PURPLE_DIM)

    def _gui_log(self, msg, tag="info"):
        """Thread-safe log append."""
        self.root.after(0, lambda m=msg, t=tag: self.log_term.log(m, t))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = Agent3Window()
    app.run()
