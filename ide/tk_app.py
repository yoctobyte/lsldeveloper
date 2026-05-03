from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from sim.console import ConsoleMessage
from sim.demo import WORLD_PROFILES

from .ai import AiSettings, OpenAiClient, apply_ai_edits
from .project import IdeProject, ProjectRuntime


class LslIdeApp(tk.Tk):
    def __init__(self, project: IdeProject):
        super().__init__()
        self.title(f"LSL Developer - {project.folder}")
        self.geometry("1180x760")
        self.project = project
        self.ai_settings = AiSettings.load()
        self.runtime: ProjectRuntime | None = None
        self.selected_object_index = 0
        self.selected_script_index = 0
        self.auto_tick = False
        self.auto_tick_after_id: str | None = None
        self.auto_tick_interval_ms = 100
        self.ai_busy = False
        self.status_var = tk.StringVar(value="Ready")
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.lines_var = tk.StringVar(value="Lines: 0")
        self.dialog_message_var = tk.StringVar(value="No active dialog")
        self.problem_rows: list[object] = []
        self._dialog_signature = None
        self._problems_signature = None
        self._fps_window_start = time.monotonic()
        self._fps_window_ticks = 0
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._refresh_lists()
        self._load_selected_script()

    def _build_ui(self):
        self._build_menu()
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Open", command=self.open_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Save", command=self.save_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(toolbar, text="Add Object", command=self.add_object).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Add Script", command=self.add_script).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(toolbar, text="Run", command=self.run_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Step", command=self.step_once).pack(side=tk.LEFT, padx=2, pady=2)
        self.auto_button = ttk.Button(toolbar, text="Auto Tick", command=self.toggle_auto_tick)
        self.auto_button.pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Touch", command=self.touch_selected_object).pack(side=tk.LEFT, padx=2, pady=2)

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, width=260)
        main.add(left, weight=0)

        ttk.Label(left, text="Objects").pack(anchor=tk.W, padx=6, pady=(6, 2))
        self.object_list = tk.Listbox(left, exportselection=False, height=8)
        self.object_list.pack(fill=tk.X, padx=6)
        self.object_list.bind("<<ListboxSelect>>", self.on_object_selected)

        ttk.Label(left, text="Scripts").pack(anchor=tk.W, padx=6, pady=(10, 2))
        self.script_list = tk.Listbox(left, exportselection=False)
        self.script_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self.script_list.bind("<<ListboxSelect>>", self.on_script_selected)

        center = ttk.Frame(main)
        main.add(center, weight=1)

        self.editor = tk.Text(center, undo=True, wrap=tk.NONE)
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.bind("<<Modified>>", self.on_editor_modified)

        ai_panel = ttk.Frame(center)
        ai_panel.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(ai_panel, text="AI").pack(anchor=tk.W, padx=4)
        self.ai_prompt = tk.Text(ai_panel, height=4, wrap=tk.WORD)
        self.ai_prompt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 2), pady=(0, 4))
        self.ai_button = ttk.Button(ai_panel, text="Ask AI", command=self.ask_ai)
        self.ai_button.pack(side=tk.RIGHT, padx=(2, 4), pady=(0, 4))

        right = ttk.Frame(main, width=380)
        main.add(right, weight=0)

        ttk.Label(right, text="Console").pack(anchor=tk.W, padx=6, pady=(6, 2))
        dialog_panel = ttk.LabelFrame(right, text="Dialog")
        dialog_panel.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(dialog_panel, textvariable=self.dialog_message_var, wraplength=340).pack(anchor=tk.W, fill=tk.X, padx=6, pady=(4, 2))
        self.dialog_buttons = ttk.Frame(dialog_panel)
        self.dialog_buttons.pack(fill=tk.X, padx=6, pady=(0, 6))
        self._refresh_dialog_panel()

        self.console = tk.Text(right, state=tk.DISABLED, wrap=tk.WORD, width=48)
        self.console.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 2))
        self._configure_console_tags()

        problems_frame = ttk.LabelFrame(right, text="Problems")
        problems_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.problems = ttk.Treeview(
            problems_frame,
            columns=("severity", "object", "script", "phase", "line", "message"),
            show="headings",
            height=5,
        )
        for column, label, width in [
            ("severity", "Type", 58),
            ("object", "Object", 86),
            ("script", "Script", 92),
            ("phase", "Phase", 72),
            ("line", "Line", 48),
            ("message", "Message", 220),
        ]:
            self.problems.heading(column, text=label)
            self.problems.column(column, width=width, stretch=column == "message")
        self.problems.pack(fill=tk.X, padx=4, pady=4)
        self.problems.bind("<Double-1>", self.open_selected_problem)

        console_input = ttk.Frame(right)
        console_input.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(console_input, text="Channel").pack(side=tk.LEFT, padx=(0, 2))
        self.channel_var = tk.StringVar(value="0")
        ttk.Entry(console_input, textvariable=self.channel_var, width=6).pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        entry = ttk.Entry(console_input, textvariable=self.input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        entry.bind("<Return>", lambda _event: self.say_input())
        ttk.Button(console_input, text="Say", command=self.say_input).pack(side=tk.LEFT)

        status = ttk.Frame(self, relief=tk.SUNKEN)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status, textvariable=self.status_var, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Label(status, textvariable=self.lines_var, width=18, anchor=tk.E).pack(side=tk.RIGHT, padx=6)
        ttk.Label(status, textvariable=self.fps_var, width=12, anchor=tk.E).pack(side=tk.RIGHT, padx=6)

    def _build_menu(self):
        menu = tk.Menu(self)
        self.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open Project...", command=self.open_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)

        project_menu = tk.Menu(menu, tearoff=False)
        project_menu.add_command(label="Add Object...", command=self.add_object)
        project_menu.add_command(label="Add Script...", command=self.add_script)
        menu.add_cascade(label="Project", menu=project_menu)

        run_menu = tk.Menu(menu, tearoff=False)
        run_menu.add_command(label="Run", command=self.run_project, accelerator="F5")
        run_menu.add_command(label="Step", command=self.step_once, accelerator="F10")
        run_menu.add_command(label="Auto Tick", command=self.toggle_auto_tick)
        run_menu.add_command(label="Touch Selected Object", command=self.touch_selected_object)
        menu.add_cascade(label="Run", menu=run_menu)

        settings_menu = tk.Menu(menu, tearoff=False)
        settings_menu.add_command(label="World Settings...", command=self.open_world_settings)
        settings_menu.add_command(label="AI Settings...", command=self.open_ai_settings)
        menu.add_cascade(label="Settings", menu=settings_menu)

        console_menu = tk.Menu(menu, tearoff=False)
        console_menu.add_command(label="Clear Console", command=self.clear_console)
        menu.add_cascade(label="Console", menu=console_menu)

        self.bind_all("<Control-o>", lambda _event: self.open_project())
        self.bind_all("<Control-s>", lambda _event: self.save_project())
        self.bind_all("<F5>", lambda _event: self.run_project())
        self.bind_all("<F10>", lambda _event: self.step_once())

    def _configure_console_tags(self):
        colors = {
            "ownersay": "#005a9c",
            "say": "#1f6f43",
            "whisper": "#4d6b2f",
            "shout": "#8f4b00",
            "im": "#6b3fa0",
            "debug": "#666666",
            "dialog": "#7c2d12",
            "ai": "#6b3fa0",
            "stub": "#9a3412",
            "error": "#b00020",
        }
        for tag, color in colors.items():
            self.console.tag_configure(tag, foreground=color)

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _selected_script_line_count(self) -> int:
        script = self.selected_script()
        if not script:
            return 0
        return len(script.source.splitlines())

    def _update_line_status(self):
        self.lines_var.set(f"Lines: {self._selected_script_line_count()}")

    def _record_tick(self):
        self._fps_window_ticks += 1
        now = time.monotonic()
        elapsed = now - self._fps_window_start
        if elapsed >= 1.0:
            self.fps_var.set(f"FPS: {self._fps_window_ticks / elapsed:.1f}")
            self._fps_window_start = now
            self._fps_window_ticks = 0

    def _reset_fps(self):
        self._fps_window_start = time.monotonic()
        self._fps_window_ticks = 0
        self.fps_var.set("FPS: 0.0")

    def _refresh_dialog_panel(self):
        if not hasattr(self, "dialog_buttons"):
            return
        dialog = getattr(self.runtime.world, "latest_dialog", None) if self.runtime else None
        signature = None
        if dialog:
            signature = (
                dialog.get("source_key", ""),
                dialog.get("source_name", ""),
                int(dialog["channel"]),
                dialog["message"],
                tuple(dialog["buttons"]),
            )
        if signature == self._dialog_signature:
            return
        self._dialog_signature = signature

        for child in self.dialog_buttons.winfo_children():
            child.destroy()
        if not dialog:
            self.dialog_message_var.set("No active dialog")
            ttk.Button(self.dialog_buttons, text="No buttons", state=tk.DISABLED).pack(side=tk.LEFT)
            return
        channel = int(dialog["channel"])
        self.dialog_message_var.set(f"{dialog['source_name']} on channel {channel}: {dialog['message']}")
        for button in dialog["buttons"]:
            ttk.Button(
                self.dialog_buttons,
                text=button,
                command=lambda value=button: self.send_dialog_response(value),
            ).pack(side=tk.LEFT, padx=(0, 4), pady=2)

    def _clear_problems(self):
        self.problem_rows = []
        self._problems_signature = None
        if hasattr(self, "problems"):
            for item in self.problems.get_children():
                self.problems.delete(item)

    def _refresh_problems(self):
        diagnostics = getattr(self.runtime.world, "diagnostics", []) if self.runtime else []
        signature = tuple(
            (
                diagnostic.severity,
                diagnostic.phase,
                diagnostic.object_name,
                diagnostic.script_name,
                diagnostic.line,
                diagnostic.column,
                diagnostic.message,
            )
            for diagnostic in diagnostics
        )
        if signature == self._problems_signature:
            return
        self._clear_problems()
        self._problems_signature = signature
        for diagnostic in diagnostics:
            self.problem_rows.append(diagnostic)
            self.problems.insert(
                "",
                tk.END,
                values=(
                    diagnostic.severity,
                    diagnostic.object_name,
                    diagnostic.script_name,
                    diagnostic.phase,
                    diagnostic.location,
                    diagnostic.message,
                ),
            )
        if diagnostics:
            self._set_status(f"{len(diagnostics)} problem(s)")

    def open_selected_problem(self, _event=None):
        selection = self.problems.selection()
        if not selection:
            return
        index = self.problems.index(selection[0])
        if index >= len(self.problem_rows):
            return
        diagnostic = self.problem_rows[index]
        for object_index, obj in enumerate(self.project.objects):
            if obj.name != diagnostic.object_name:
                continue
            for script_index, script in enumerate(obj.scripts):
                if script.name != diagnostic.script_name:
                    continue
                self.save_current_editor()
                self.selected_object_index = object_index
                self.selected_script_index = script_index
                self._refresh_lists()
                self._load_selected_script()
                if diagnostic.line:
                    self.editor.mark_set(tk.INSERT, f"{diagnostic.line}.{max((diagnostic.column or 1) - 1, 0)}")
                    self.editor.see(tk.INSERT)
                return

    def _stop_auto_tick(self):
        self.auto_tick = False
        if self.auto_tick_after_id:
            self.after_cancel(self.auto_tick_after_id)
            self.auto_tick_after_id = None
        if hasattr(self, "auto_button"):
            self.auto_button.configure(text="Auto Tick")

    def _refresh_lists(self):
        self.object_list.delete(0, tk.END)
        for obj in self.project.objects:
            self.object_list.insert(tk.END, obj.name)
        if self.project.objects:
            self.selected_object_index = min(self.selected_object_index, len(self.project.objects) - 1)
            self.object_list.selection_set(self.selected_object_index)
        self._refresh_script_list()

    def _refresh_script_list(self):
        self.script_list.delete(0, tk.END)
        obj = self.selected_object()
        if not obj:
            return
        for script in obj.scripts:
            self.script_list.insert(tk.END, script.name)
        if obj.scripts:
            self.selected_script_index = min(self.selected_script_index, len(obj.scripts) - 1)
            self.script_list.selection_set(self.selected_script_index)

    def selected_object(self):
        if not self.project.objects:
            return None
        return self.project.objects[self.selected_object_index]

    def selected_script(self):
        obj = self.selected_object()
        if not obj or not obj.scripts:
            return None
        return obj.scripts[self.selected_script_index]

    def save_current_editor(self):
        script = self.selected_script()
        if script:
            script.source = self.editor.get("1.0", tk.END).rstrip() + "\n"

    def _load_selected_script(self):
        script = self.selected_script()
        self.editor.delete("1.0", tk.END)
        if script:
            self.editor.insert("1.0", script.source)
        self.editor.edit_modified(False)
        self._update_line_status()

    def on_object_selected(self, _event=None):
        selection = self.object_list.curselection()
        if not selection:
            return
        self.save_current_editor()
        self.selected_object_index = selection[0]
        self.selected_script_index = 0
        self._refresh_script_list()
        self._load_selected_script()

    def on_script_selected(self, _event=None):
        selection = self.script_list.curselection()
        if not selection:
            return
        self.save_current_editor()
        self.selected_script_index = selection[0]
        self._load_selected_script()

    def open_project(self):
        folder = filedialog.askdirectory(initialdir=str(self.project.folder))
        if folder:
            self._stop_auto_tick()
            self.save_current_editor()
            self.project = IdeProject.load(folder)
            self.runtime = None
            self._refresh_dialog_panel()
            self._clear_problems()
            self.title(f"LSL Developer - {self.project.folder}")
            self.selected_object_index = 0
            self.selected_script_index = 0
            self._refresh_lists()
            self._load_selected_script()
            self._set_status(f"Opened {self.project.folder}")

    def save_project(self):
        self.save_current_editor()
        self.project.save()
        self._update_line_status()
        self._set_status(f"Saved {self.project.path}")
        self.append_console(ConsoleMessage("debug", f"saved {self.project.path}"))

    def open_ai_settings(self):
        dialog = tk.Toplevel(self)
        dialog.title("AI Settings")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="OpenAI API Key").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        key_var = tk.StringVar(value=self.ai_settings.api_key)
        key_entry = ttk.Entry(frame, textvariable=key_var, show="*", width=52)
        key_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))

        ttk.Label(frame, text="Model").grid(row=2, column=0, sticky=tk.W, pady=(0, 4))
        model_var = tk.StringVar(value=self.ai_settings.model)
        model_box = ttk.Combobox(
            frame,
            textvariable=model_var,
            values=[
                "gpt-5.2",
                "gpt-5.2-codex",
                "gpt-5.1",
                "gpt-5.1-codex",
                "gpt-5-mini",
                "gpt-4.1",
            ],
            width=28,
        )
        model_box.grid(row=3, column=0, sticky=tk.W, pady=(0, 12))

        def save():
            self.ai_settings.api_key = key_var.get().strip()
            self.ai_settings.model = model_var.get().strip() or self.ai_settings.model
            self.ai_settings.save()
            self._set_status("AI settings saved")
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky=tk.E)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side=tk.RIGHT)
        frame.columnconfigure(0, weight=1)
        key_entry.focus_set()

    def open_world_settings(self):
        dialog = tk.Toplevel(self)
        dialog.title("World Settings")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Avatar Profile").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        profile_var = tk.StringVar(value=self.project.world_profile)
        profile_box = ttk.Combobox(
            frame,
            textvariable=profile_var,
            values=list(WORLD_PROFILES),
            state="readonly",
            width=24,
        )
        profile_box.grid(row=1, column=0, sticky=tk.W, pady=(0, 12))

        count_var = tk.StringVar()

        def update_count(*_args):
            profile = profile_var.get()
            count_var.set(f"Avatars: {WORLD_PROFILES.get(profile, 0)}")

        profile_var.trace_add("write", update_count)
        ttk.Label(frame, textvariable=count_var).grid(row=2, column=0, sticky=tk.W, pady=(0, 12))
        update_count()

        def save():
            self.project.world_profile = profile_var.get()
            self.project.save()
            self.runtime = None
            self._refresh_dialog_panel()
            self._clear_problems()
            self._set_status(f"World profile: {self.project.world_profile}")
            self.append_console(ConsoleMessage("debug", f"world profile set to {self.project.world_profile}"))
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, sticky=tk.E)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side=tk.RIGHT)
        profile_box.focus_set()

    def ask_ai(self):
        if self.ai_busy:
            return
        question = self.ai_prompt.get("1.0", tk.END).strip()
        if not question:
            messagebox.showerror("Missing Question", "Enter a question or change request for the AI.")
            return
        self.save_current_editor()
        self.ai_busy = True
        self.ai_button.configure(state=tk.DISABLED)
        self._set_status("AI request running")
        self.append_console(ConsoleMessage("ai", f"question: {question}"))

        def worker():
            try:
                result = OpenAiClient(self.ai_settings).ask_project(self.project, question)
                self.after(0, lambda result=result: self._finish_ai_success(result))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._finish_ai_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_ai_success(self, result):
        changed = apply_ai_edits(self.project, result.edits)
        if changed:
            self.project.save()
            self._load_selected_script()
        self.ai_busy = False
        self.ai_button.configure(state=tk.NORMAL)
        self.append_console(ConsoleMessage("ai", result.answer or "AI completed."))
        if changed:
            self.append_console(ConsoleMessage("debug", "AI edited " + ", ".join(changed)))
            self._set_status(f"AI edited {len(changed)} script(s)")
        else:
            self._set_status("AI answered without edits")

    def _finish_ai_error(self, exc: Exception):
        self.ai_busy = False
        self.ai_button.configure(state=tk.NORMAL)
        self._set_status("AI request failed")
        self.append_console(ConsoleMessage("error", str(exc)))

    def add_object(self):
        self.save_current_editor()
        name = simpledialog.askstring("Add Object", "Object name:", initialvalue=f"Object {len(self.project.objects) + 1}")
        obj = self.project.add_object(name or None)
        self.selected_object_index = self.project.objects.index(obj)
        self.selected_script_index = 0
        self._refresh_lists()
        self._load_selected_script()

    def add_script(self):
        if not self.project.objects:
            self.project.add_object()
        self.save_current_editor()
        obj = self.selected_object()
        name = simpledialog.askstring("Add Script", "Script name:", initialvalue=f"script{len(obj.scripts) + 1}.lsl")
        script = self.project.add_script(self.selected_object_index, name or None)
        self.selected_script_index = obj.scripts.index(script)
        self._refresh_script_list()
        self._load_selected_script()

    def run_project(self):
        self._stop_auto_tick()
        self.save_current_editor()
        self.clear_console()
        self._clear_problems()
        self._reset_fps()
        try:
            self.runtime = self.project.build_runtime(echo_stdout=False)
            for message in self.runtime.world.console.messages:
                self.append_console(message)
            self.runtime.world.console.add_listener(self.append_console)
            self.runtime.tick()
            self._refresh_dialog_panel()
            self._refresh_problems()
            self._record_tick()
            self._update_line_status()
            if not self.runtime.world.diagnostics:
                self._set_status("Runtime started")
            self.append_console(ConsoleMessage("debug", "runtime started"))
        except Exception as exc:
            self.runtime = None
            self._refresh_dialog_panel()
            self._refresh_problems()
            self._set_status("Runtime error")
            self.append_console(ConsoleMessage("error", str(exc)))

    def _tick_runtime_once(self, status_text: str | None = None):
        if not self.runtime:
            return
        self.runtime.tick()
        self._refresh_dialog_panel()
        self._refresh_problems()
        self._record_tick()
        if status_text and not self.runtime.world.diagnostics:
            self._set_status(status_text)

    def step_once(self):
        if not self.runtime:
            self.run_project()
            return
        try:
            self._tick_runtime_once(f"Stepped frame {self.runtime.loop.tick_count + 1}")
        except Exception as exc:
            self._stop_auto_tick()
            self._set_status("Runtime error")
            self.append_console(ConsoleMessage("error", str(exc)))

    def toggle_auto_tick(self):
        if self.auto_tick:
            self._stop_auto_tick()
            self._set_status("Auto tick stopped")
            return
        if not self.runtime:
            self.run_project()
        if not self.runtime:
            return
        self.auto_tick = True
        self.auto_button.configure(text="Stop Auto")
        self._set_status("Auto ticking")
        self._schedule_auto_tick()

    def _schedule_auto_tick(self):
        if self.auto_tick:
            self.auto_tick_after_id = self.after(self.auto_tick_interval_ms, self._auto_tick_once)

    def _auto_tick_once(self):
        self.auto_tick_after_id = None
        if not self.auto_tick or not self.runtime:
            return
        try:
            self.runtime.tick()
            self._refresh_dialog_panel()
            self._refresh_problems()
            self._record_tick()
            if not self.runtime.world.diagnostics:
                self._set_status(f"Auto ticking frame {self.runtime.loop.tick_count}")
        except Exception as exc:
            self._stop_auto_tick()
            self._set_status("Runtime error")
            self.append_console(ConsoleMessage("error", str(exc)))
            return
        self._schedule_auto_tick()

    def touch_selected_object(self):
        if not self.runtime:
            self.run_project()
        obj = self.selected_object()
        if self.runtime and obj:
            self.runtime.touch(obj.name)
            if self.auto_tick:
                self._set_status(f"Touched {obj.name}")
            else:
                self.step_once()

    def say_input(self):
        text = self.input_var.get()
        if not text:
            return
        if not self.runtime:
            self.run_project()
        try:
            channel = int(self.channel_var.get() or "0")
        except ValueError:
            messagebox.showerror("Invalid Channel", "Channel must be an integer.")
            return
        if self.runtime:
            self.runtime.say(text, channel)
            if self.auto_tick:
                self._set_status(f"Sent chat on channel {channel}")
            else:
                self._tick_runtime_once(f"Sent chat on channel {channel}")
        self.input_var.set("")

    def clear_console(self):
        self.console.configure(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.configure(state=tk.DISABLED)

    def append_console(self, message: ConsoleMessage):
        tag = message.message_type
        prefix = tag.upper()
        if message.channel is not None:
            prefix += f"[{message.channel}]"
        if message.source_name:
            prefix += f" {message.source_name}"
        line = f"{prefix}: {message.text}\n"
        self.console.configure(state=tk.NORMAL)
        self.console.insert(tk.END, line, tag)
        self.console.see(tk.END)
        self.console.configure(state=tk.DISABLED)
        if message.message_type == "dialog":
            self._refresh_dialog_panel()

    def send_dialog_response(self, button: str):
        if not self.runtime:
            return
        self.runtime.dialog_response(button)
        if self.auto_tick:
            self._set_status(f"Dialog response: {button}")
        else:
            self._tick_runtime_once(f"Dialog response: {button}")

    def on_editor_modified(self, _event=None):
        if self.editor.edit_modified():
            self.save_current_editor()
            self._update_line_status()
            self.editor.edit_modified(False)

    def close(self):
        self._stop_auto_tick()
        self.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the Tk LSL developer IDE.")
    parser.add_argument("project", nargs="?", default="lsl_project", help="Project data folder")
    args = parser.parse_args(argv)
    project = IdeProject.load(Path(args.project))
    app = LslIdeApp(project)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
