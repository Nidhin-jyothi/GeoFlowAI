"""
GeoFlowAI — Agent 1 Planner GUI
Iron-Man / JARVIS HUD aesthetic
Uses only tkinter (no extra GUI dependencies).
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import math
import time
import os
import config

# ── Colour Palette ──────────────────────────────────────────────
BG           = "#0a0e17"
BG_PANEL     = "#0d1320"
CYAN         = "#00d4ff"
CYAN_DIM     = "#006680"
CYAN_GLOW    = "#00a8cc"
AMBER        = "#ff9f1c"
AMBER_DIM    = "#7a4c0e"
RED          = "#ff3d3d"
WHITE        = "#e0e6ed"
GREY         = "#3a4556"
DARK_GREY    = "#1a2233"

# ── Arc-Reactor spinner parameters ──────────────────────────────
ARC_SIZE     = 120          # canvas size
ARC_R_OUTER  = 50           # outer ring radius
ARC_R_INNER  = 30           # inner ring radius
ARC_SPEED    = 4            # degrees per frame


class HUDFrame(tk.Frame):
    """Utility: a frame with a thin cyan border to look like a HUD panel."""

    def __init__(self, master, highlight=CYAN_DIM, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("highlightbackground", highlight)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 10)
        super().__init__(master, **kw)


class ArcReactorSpinner(tk.Canvas):
    """Animated arc-reactor style loading spinner."""

    def __init__(self, master, size=ARC_SIZE, **kw):
        kw.setdefault("bg", BG)
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, width=size, height=size, **kw)
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.angle = 0
        self.running = False
        self._items = []

    # ── drawing ──
    def _draw(self):
        self.delete("spinner")
        cx, cy = self.cx, self.cy

        # Outer rotating arcs (3 segments, 80° each, spaced 120° apart)
        for i in range(3):
            start = self.angle + i * 120
            self.create_arc(
                cx - ARC_R_OUTER, cy - ARC_R_OUTER,
                cx + ARC_R_OUTER, cy + ARC_R_OUTER,
                start=start, extent=80,
                outline=CYAN, width=2, style="arc", tags="spinner"
            )

        # Inner counter-rotating arcs
        for i in range(4):
            start = -self.angle * 1.5 + i * 90
            self.create_arc(
                cx - ARC_R_INNER, cy - ARC_R_INNER,
                cx + ARC_R_INNER, cy + ARC_R_INNER,
                start=start, extent=60,
                outline=CYAN_GLOW, width=2, style="arc", tags="spinner"
            )

        # Centre dot
        r = 5
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=CYAN, outline=CYAN, tags="spinner")

        # Tiny orbiting dots
        for i in range(6):
            a = math.radians(self.angle * 2 + i * 60)
            dx = int(math.cos(a) * (ARC_R_OUTER + 8))
            dy = int(math.sin(a) * (ARC_R_OUTER + 8))
            dr = 2
            self.create_oval(cx+dx-dr, cy+dy-dr, cx+dx+dr, cy+dy+dr,
                             fill=AMBER, outline=AMBER, tags="spinner")

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


class TypewriterText(tk.Text):
    """Text widget that reveals content character-by-character."""

    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_PANEL)
        kw.setdefault("fg", WHITE)
        kw.setdefault("insertbackground", CYAN)
        kw.setdefault("selectbackground", CYAN_DIM)
        kw.setdefault("relief", "flat")
        kw.setdefault("wrap", "word")
        kw.setdefault("padx", 12)
        kw.setdefault("pady", 10)
        kw.setdefault("state", "disabled")
        kw.setdefault("highlightbackground", CYAN_DIM)
        kw.setdefault("highlightthickness", 1)
        super().__init__(master, **kw)
        self._queue = ""
        self._idx = 0
        self._typing = False

        # Styling tags
        self.tag_configure("step_header", foreground=AMBER, font=("Consolas", 11, "bold"))
        self.tag_configure("bullet", foreground=CYAN)
        self.tag_configure("algorithm", foreground=CYAN_GLOW, font=("Consolas", 10, "bold"))
        self.tag_configure("normal", foreground=WHITE)

    def typewrite(self, text, speed=8):
        """Start typing text. speed = chars per frame (≈30 fps)."""
        self._queue = text
        self._idx = 0
        self._speed = speed
        self._typing = True
        self.configure(state="normal")
        self.delete("1.0", "end")
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
            self._apply_highlights()
            return
        self.after(30, self._tick)

    def set_text_instant(self, text):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("end", text)
        self.configure(state="disabled")
        self._apply_highlights()

    def _apply_highlights(self):
        """Apply colour tags to step headers and bullets after text is complete."""
        self.configure(state="normal")
        # Highlight lines starting with **Step
        line_count = int(self.index("end-1c").split(".")[0])
        for i in range(1, line_count + 1):
            line = self.get(f"{i}.0", f"{i}.end")
            if line.strip().startswith("**Step") or line.strip().startswith("###"):
                self.tag_add("step_header", f"{i}.0", f"{i}.end")
            elif line.strip().startswith("*") or line.strip().startswith("-") or line.strip().startswith("+"):
                self.tag_add("bullet", f"{i}.0", f"{i}.end")
        self.configure(state="disabled")


class Agent1Window:
    """Main GUI window for Agent 1 — the Planner."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G E O F L O W  A I  ·  A G E N T  1  ·  P L A N N E R")
        self.root.configure(bg=BG)
        self.root.geometry("960x720")
        self.root.minsize(800, 600)

        # ── Fonts ──
        self.font_title  = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.font_sub    = tkfont.Font(family="Consolas", size=10)
        self.font_input  = tkfont.Font(family="Consolas", size=11)
        self.font_btn    = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.font_status = tkfont.Font(family="Consolas", size=9)
        self.font_output = tkfont.Font(family="Consolas", size=10)

        self._build_ui()
        self._status_pulse_on = True

    # ──────────────────────────────────────────────────────────────
    #  UI Construction
    # ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top bar ──
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 4))

        tk.Label(top, text="◈  GEOFLOW AI", font=self.font_title,
                 fg=CYAN, bg=BG).pack(side="left")
        tk.Label(top, text="AGENT 1 · STRATEGIC PLANNER", font=self.font_sub,
                 fg=AMBER, bg=BG).pack(side="right")

        # Separator line
        sep = tk.Canvas(self.root, height=2, bg=BG, highlightthickness=0)
        sep.pack(fill="x", padx=20, pady=(2, 8))
        sep.create_line(0, 1, 2000, 1, fill=CYAN_DIM, width=1)

        # ── Input Section ──
        input_frame = HUDFrame(self.root)
        input_frame.pack(fill="x", padx=20, pady=(4, 8))

        tk.Label(input_frame, text="▸ MISSION QUERY", font=self.font_sub,
                 fg=CYAN, bg=BG_PANEL).pack(anchor="w")

        entry_frame = tk.Frame(input_frame, bg=BG_PANEL)
        entry_frame.pack(fill="x", pady=(6, 0))

        self.query_entry = tk.Entry(
            entry_frame, font=self.font_input,
            bg=DARK_GREY, fg=WHITE, insertbackground=CYAN,
            relief="flat", highlightbackground=CYAN_DIM,
            highlightthickness=1, highlightcolor=CYAN
        )
        self.query_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.query_entry.insert(0, "Clip the Kerala DEM using the state boundary shapefile, then calculate the slope of the clipped DEM.")
        self.query_entry.bind("<Return>", lambda e: self._on_generate())

        self.gen_btn = tk.Button(
            entry_frame, text="⚡ GENERATE PLAN", font=self.font_btn,
            bg=CYAN_DIM, fg=WHITE, activebackground=CYAN,
            activeforeground=BG, relief="flat", padx=16, pady=4,
            cursor="hand2", command=self._on_generate
        )
        self.gen_btn.pack(side="right", padx=(10, 0))

        # ── Status bar ──
        status_bar = tk.Frame(self.root, bg=BG)
        status_bar.pack(fill="x", padx=20)

        self.status_label = tk.Label(
            status_bar, text="STATUS: AWAITING INPUT", font=self.font_status,
            fg=GREY, bg=BG, anchor="w"
        )
        self.status_label.pack(side="left")

        self.model_label = tk.Label(
            status_bar, text=f"MODEL: gemini-2.5-flash  ·  RAG: checking…",
            font=self.font_status, fg=GREY, bg=BG, anchor="e"
        )
        self.model_label.pack(side="right")

        # ── Spinner + Output (center area) ──
        center = tk.Frame(self.root, bg=BG)
        center.pack(fill="both", expand=True, padx=20, pady=(8, 4))

        # Spinner (hidden initially)
        self.spinner_frame = tk.Frame(center, bg=BG)
        self.spinner = ArcReactorSpinner(self.spinner_frame)
        self.spinner.pack()
        self.thinking_label = tk.Label(
            self.spinner_frame, text="AGENT 1 · ANALYZING…",
            font=self.font_sub, fg=CYAN, bg=BG
        )
        self.thinking_label.pack(pady=(8, 0))

        # Output text
        self.output_frame = HUDFrame(center, highlight=CYAN_DIM)
        self.output_frame.pack(fill="both", expand=True)

        tk.Label(self.output_frame, text="▸ WORKFLOW PLAN", font=self.font_sub,
                 fg=CYAN, bg=BG_PANEL).pack(anchor="w")

        self.output_text = TypewriterText(self.output_frame, font=self.font_output)
        self.output_text.pack(fill="both", expand=True, pady=(6, 0))

        # Placeholder
        self.output_text.set_text_instant(
            "  Awaiting mission parameters…\n\n"
            "  Enter your geospatial query above and press ⚡ GENERATE PLAN.\n"
        )

        # ── Bottom bar ──
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(4, 12))

        self.save_btn = tk.Button(
            bottom, text="💾 SAVE PLAN", font=self.font_btn,
            bg=DARK_GREY, fg=GREY, relief="flat", padx=14, pady=3,
            state="disabled", cursor="hand2", command=self._on_save
        )
        self.save_btn.pack(side="left")

        self.char_count = tk.Label(
            bottom, text="", font=self.font_status, fg=GREY, bg=BG
        )
        self.char_count.pack(side="right")

        # Separator
        sep2 = tk.Canvas(self.root, height=1, bg=BG, highlightthickness=0)
        sep2.pack(fill="x", padx=20, side="bottom")
        sep2.create_line(0, 0, 2000, 0, fill=CYAN_DIM, width=1)

    # ──────────────────────────────────────────────────────────────
    #  Actions
    # ──────────────────────────────────────────────────────────────
    def _set_status(self, text, colour=CYAN):
        self.status_label.configure(text=f"STATUS: {text}", fg=colour)

    def _show_spinner(self):
        self.output_frame.pack_forget()
        self.spinner_frame.pack(expand=True)
        self.spinner.start()

    def _hide_spinner(self):
        self.spinner.stop()
        self.spinner_frame.pack_forget()
        self.output_frame.pack(fill="both", expand=True)

    def _on_generate(self):
        query = self.query_entry.get().strip()
        if not query:
            self._set_status("ERROR: EMPTY QUERY", RED)
            return

        # Disable input
        self.gen_btn.configure(state="disabled", bg=GREY)
        self.query_entry.configure(state="disabled")
        self.save_btn.configure(state="disabled", bg=DARK_GREY, fg=GREY)

        self._set_status("INITIALIZING AGENT 1…", AMBER)
        self._show_spinner()
        self._pulse_thinking()

        # Run in background thread
        threading.Thread(target=self._run_planner, args=(query,), daemon=True).start()

    def _pulse_thinking(self):
        """Cycle the thinking label text for visual liveliness."""
        if not self.spinner.running:
            return
        phases = [
            "AGENT 1 · ANALYZING…",
            "AGENT 1 · REASONING…",
            "AGENT 1 · PLANNING…",
            "AGENT 1 · SYNTHESIZING…",
        ]
        current = self.thinking_label.cget("text")
        try:
            idx = phases.index(current)
        except ValueError:
            idx = -1
        self.thinking_label.configure(text=phases[(idx + 1) % len(phases)])
        self.root.after(1200, self._pulse_thinking)

    def _run_planner(self, query):
        """Background: import & run Agent1Planner, then update GUI."""
        try:
            self.root.after(0, lambda: self._set_status("LOADING PLANNER MODULE…", AMBER))

            from agent1_planner import Agent1Planner
            planner = Agent1Planner()

            rag_status = "ACTIVE" if planner.retriever else "OFFLINE"
            self.root.after(0, lambda: self.model_label.configure(
                text=f"MODEL: {planner.model}  ·  RAG: {rag_status}"
            ))
            self.root.after(0, lambda: self._set_status("GENERATING WORKFLOW PLAN…", CYAN))

            plan = planner.generate_plan(query)
            self._plan_text = plan

            # Update GUI on main thread
            self.root.after(0, lambda: self._on_plan_ready(plan))

        except Exception as e:
            self.root.after(0, lambda: self._on_plan_error(str(e)))

    def _on_plan_ready(self, plan):
        self._hide_spinner()
        self._set_status("PLAN GENERATED SUCCESSFULLY", CYAN)
        self.output_text.typewrite(plan, speed=12)
        self.char_count.configure(text=f"{len(plan)} chars  ·  {len(plan.splitlines())} lines")

        # Re-enable controls
        self.gen_btn.configure(state="normal", bg=CYAN_DIM)
        self.query_entry.configure(state="normal")
        self.save_btn.configure(state="normal", bg=AMBER_DIM, fg=WHITE)

    def _on_plan_error(self, err):
        self._hide_spinner()
        self._set_status(f"ERROR: {err[:80]}", RED)
        self.output_text.set_text_instant(f"⛔  Plan generation failed:\n\n{err}")

        self.gen_btn.configure(state="normal", bg=CYAN_DIM)
        self.query_entry.configure(state="normal")

    def _on_save(self):
        if not hasattr(self, "_plan_text"):
            return
        path = os.path.join(config.OUTPUT_DIR, "step1_plan.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._plan_text)
        self._set_status(f"PLAN SAVED → {path}", CYAN)

    # ──────────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = Agent1Window()
    app.run()
