"""
GeoFlowAI — Unified Pipeline Orchestrator
==========================================
Runs the full Agent 1 → Agent 2 → Agent 3 pipeline in a single process.
Agent 1 opens first. On plan generation, Agent 2 pops up and auto-executes.
On schema generation, Agent 3 pops up and auto-executes the full pipeline.
All windows stay open.
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import os
import json
import time
import config

# ── Shared palette ──────────────────────────────────────────────
BG        = "#0a0e17"
CYAN      = "#00d4ff"
CYAN_DIM  = "#006680"
AMBER     = "#ff9f1c"
AMBER_DIM = "#7a4c0e"
WHITE     = "#e0e6ed"
GREY      = "#3a4556"
RED       = "#ff3d3d"
GREEN     = "#00ff7f"
PURPLE    = "#bc13fe"


class PipelineOrchestrator:
    """
    Coordinates Agent 1 → Agent 2 → Agent 3 in one Tk application.
    Agent 1 runs in the root window; Agent 2 and Agent 3 open as
    Toplevel windows that auto-execute and remain open.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # hide root; Agent1 will be a Toplevel too

        self.agent1_win = None
        self.agent2_win = None
        self.agent3_win = None

        self._launch_agent1()

    # ──────────────────────────────────────────────────────────────
    #  AGENT 1 — Planner
    # ──────────────────────────────────────────────────────────────
    def _launch_agent1(self):
        """Create Agent 1 window (plan generation)."""
        from gui_agent1 import Agent1Window, CYAN, AMBER_DIM, GREY, DARK_GREY, RED

        # Monkey-patch Agent1Window to use a Toplevel attached to our root
        win = Agent1Window.__new__(Agent1Window)

        # Create Toplevel instead of Tk
        win.root = tk.Toplevel(self.root)
        win.root.title("G E O F L O W  A I  ·  A G E N T  1  ·  P L A N N E R")
        win.root.configure(bg="#0a0e17")
        win.root.geometry("960x720")
        win.root.minsize(800, 600)
        win.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Fonts
        win.font_title  = tkfont.Font(family="Consolas", size=16, weight="bold")
        win.font_sub    = tkfont.Font(family="Consolas", size=10)
        win.font_input  = tkfont.Font(family="Consolas", size=11)
        win.font_btn    = tkfont.Font(family="Consolas", size=10, weight="bold")
        win.font_status = tkfont.Font(family="Consolas", size=9)
        win.font_output = tkfont.Font(family="Consolas", size=10)

        win._build_ui()
        win._status_pulse_on = True

        # Override _on_plan_ready to auto-chain to Agent 2
        original_ready = win._on_plan_ready
        def chained_ready(plan):
            original_ready(plan)
            # Auto-save the plan
            path = os.path.join(config.OUTPUT_DIR, "step1_plan.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(plan)
            win._set_status(f"PLAN SAVED → launching Agent 2…", CYAN)
            # Launch Agent 2 after a short delay
            win.root.after(3000, self._launch_agent2)
        win._on_plan_ready = chained_ready

        self.agent1_win = win

    # ──────────────────────────────────────────────────────────────
    #  AGENT 2 — Schematizer
    # ──────────────────────────────────────────────────────────────
    def _launch_agent2(self):
        """Create Agent 2 window and auto-trigger structuring."""
        from gui_agent2 import (Agent2Window, HUDFrame, DataStreamSpinner,
                                JSONTypewriter, BG, BG_PANEL, AMBER, AMBER_DIM,
                                AMBER_GLOW, CYAN, CYAN_DIM, WHITE, GREY, DARK_GREY, RED)

        win = Agent2Window.__new__(Agent2Window)
        win.root = tk.Toplevel(self.root)
        win.root.title("G E O F L O W  A I  ·  A G E N T  2  ·  S C H E M A T I Z E R")
        win.root.configure(bg=BG)
        win.root.geometry("1000x750")

        win.font_title  = tkfont.Font(family="Consolas", size=16, weight="bold")
        win.font_sub    = tkfont.Font(family="Consolas", size=10)
        win.font_btn    = tkfont.Font(family="Consolas", size=10, weight="bold")
        win.font_output = tkfont.Font(family="Consolas", size=10)

        win._build_ui()

        # Override _on_ready to auto-save and chain to Agent 3
        original_ready = win._on_ready
        def chained_ready(json_str):
            original_ready(json_str)
            # Auto-save
            if hasattr(win, "_schema_data"):
                path = os.path.join(config.OUTPUT_DIR, "workflow_plan.json")
                with open(path, "w") as f:
                    json.dump(win._schema_data["steps"], f, indent=2)
                win.status_label.configure(text=f"SCHEMA SAVED → launching Agent 3…", fg=CYAN)
            # Launch Agent 3 after a short delay
            win.root.after(3000, self._launch_agent3)
        win._on_ready = chained_ready

        self.agent2_win = win

        # Auto-trigger the structuring after the window appears
        win.root.after(500, win._on_structure)

    # ──────────────────────────────────────────────────────────────
    #  AGENT 3 — Code Generator + Executor
    # ──────────────────────────────────────────────────────────────
    def _launch_agent3(self):
        """Create Agent 3 window and auto-start the pipeline."""
        from gui_agent3 import (Agent3Window, HUDFrame, CodeParticleSpinner,
                                PipelineTerminal, BG, BG_PANEL, PURPLE, PURPLE_DIM,
                                PURPLE_GLOW, CYAN, AMBER, WHITE, GREY, DARK_GREY,
                                RED, GREEN, STATUS_COLORS)
        from tkinter import ttk

        win = Agent3Window.__new__(Agent3Window)
        win.root = tk.Toplevel(self.root)
        win.root.title("G E O F L O W  A I  ·  A G E N T  3  ·  C O D E  G E N  +  E X E C U T E")
        win.root.configure(bg=BG)
        win.root.geometry("1200x850")

        win.font_title = tkfont.Font(family="Consolas", size=16, weight="bold")
        win.font_sub   = tkfont.Font(family="Consolas", size=10)
        win.font_btn   = tkfont.Font(family="Consolas", size=10, weight="bold")
        win.font_code  = tkfont.Font(family="Consolas", size=10)

        win.workflow_data = []
        win.step_status   = {}
        win._is_running   = False

        win._build_ui()
        win._load_workflow()

        self.agent3_win = win

        # Override _pipeline_finished to auto-open QGIS
        original_finished = win._pipeline_finished
        def auto_open_qgis():
            original_finished()
            # Auto-open in QGIS after pipeline completes
            win.root.after(2000, win._open_in_qgis)
        win._pipeline_finished = auto_open_qgis

        # Auto-start the pipeline after the window appears
        win.root.after(2000, win._on_start_pipeline)

    # ──────────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────────
    def _on_close(self):
        """Called when Agent 1 is closed — tear down everything."""
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PipelineOrchestrator()
    app.run()
