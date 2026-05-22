from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
import json
import os

RECENT_PROJECTS_FILE = os.path.expanduser("~/.config/lsldeveloper/recent_projects.json")

def load_recent_projects() -> list[str]:
    try:
        if os.path.exists(RECENT_PROJECTS_FILE):
            with open(RECENT_PROJECTS_FILE, "r", encoding="utf-8") as f:
                paths = json.load(f)
                if isinstance(paths, list):
                    return [p for p in paths if os.path.isdir(p)]
    except Exception:
        pass
    return []

def save_recent_projects(paths: list[str]):
    try:
        os.makedirs(os.path.dirname(RECENT_PROJECTS_FILE), exist_ok=True)
        with open(RECENT_PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(paths, f, indent=2)
    except Exception:
        pass

from sim.console import ConsoleMessage
from sim.demo import WORLD_PROFILES

from .ai import AiSettings, OpenAiClient, apply_ai_edits
from .project import IdeProject, ProjectRuntime


class LslIdeApp(tk.Tk):
    def __init__(self, project: IdeProject):
        super().__init__()
        self.title(f"LSL Developer - {project.folder}")
        self.geometry("1280x800")
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
        self.fps_var = tk.StringVar(value="Frame: 0 | FPS: 0.0")
        self.lines_var = tk.StringVar(value="Lines: 0")
        self.dialog_message_var = tk.StringVar(value="No active dialog")
        self.problem_rows: list[object] = []
        self._dialog_signature = object()
        self._problems_signature = None
        self._fps_window_start = time.monotonic()
        self._fps_window_ticks = 0
        self._last_fps = 0.0
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._refresh_lists()
        self._load_selected_script()
        self._add_to_recent(project.folder)

    def _build_ui(self):
        self._build_menu()
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="New", command=self.new_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Open", command=self.open_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Save", command=self.save_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(toolbar, text="Add Object", command=self.add_object).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Add Script", command=self.add_script).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Add Notecard", command=self.add_notecard).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Obj Settings", command=self.open_object_settings).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(toolbar, text="Run", command=self.run_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Step", command=self.step_once).pack(side=tk.LEFT, padx=2, pady=2)
        self.auto_button = ttk.Button(toolbar, text="Auto Tick", command=self.toggle_auto_tick)
        self.auto_button.pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Stop", command=self.stop_project).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Touch", command=self.touch_selected_object).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Adv Touch", command=self.open_advanced_touch).pack(side=tk.LEFT, padx=2, pady=2)

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, width=260)
        main.add(left, weight=0)

        ttk.Label(left, text="Objects").pack(anchor=tk.W, padx=6, pady=(6, 2))
        self.object_list = tk.Listbox(left, exportselection=False, height=8)
        self.object_list.pack(fill=tk.X, padx=6)
        self.object_list.bind("<<ListboxSelect>>", self.on_object_selected)

        ttk.Label(left, text="Scripts & Notecards").pack(anchor=tk.W, padx=6, pady=(10, 2))
        self.script_list = tk.Listbox(left, exportselection=False)
        self.script_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self.script_list.bind("<<ListboxSelect>>", self.on_script_selected)

        center = ttk.Frame(main)
        main.add(center, weight=1)

        editor_container = ttk.Frame(center)
        editor_container.pack(fill=tk.BOTH, expand=True)

        self.editor = tk.Text(editor_container, undo=True, wrap=tk.NONE)
        v_scroll = ttk.Scrollbar(editor_container, orient=tk.VERTICAL, command=self.editor.yview)
        h_scroll = ttk.Scrollbar(editor_container, orient=tk.HORIZONTAL, command=self.editor.xview)
        self.editor.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.editor.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        editor_container.rowconfigure(0, weight=1)
        editor_container.columnconfigure(0, weight=1)

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

        # Dialog Panel (stays static at top)
        dialog_panel = ttk.LabelFrame(right, text="Dialog")
        dialog_panel.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 4))
        ttk.Label(dialog_panel, textvariable=self.dialog_message_var, wraplength=340).pack(anchor=tk.W, fill=tk.X, padx=6, pady=(4, 2))
        self.dialog_buttons = ttk.Frame(dialog_panel)
        self.dialog_buttons.pack(fill=tk.X, padx=6, pady=(0, 6))
        self._refresh_dialog_panel()

        # Console Input Panel (stays static at bottom)
        console_input = ttk.Frame(right)
        console_input.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(4, 6))
        ttk.Label(console_input, text="Channel").pack(side=tk.LEFT, padx=(0, 2))
        self.channel_var = tk.StringVar(value="0")
        ttk.Entry(console_input, textvariable=self.channel_var, width=6).pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        entry = ttk.Entry(console_input, textvariable=self.input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        entry.bind("<Return>", lambda _event: self.say_input())
        ttk.Button(console_input, text="Say", command=self.say_input).pack(side=tk.LEFT)

        # Vertical PanedWindow in the middle
        right_paned = ttk.PanedWindow(right, orient=tk.VERTICAL)
        right_paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)

        # Pane 1: Console Frame
        console_pane = ttk.Frame(right_paned)
        right_paned.add(console_pane, weight=2)
        ttk.Label(console_pane, text="Console").pack(anchor=tk.W, pady=(0, 2))
        console_container = ttk.Frame(console_pane)
        console_container.pack(fill=tk.BOTH, expand=True)
        self.console = tk.Text(console_container, state=tk.DISABLED, wrap=tk.WORD, width=48)
        self.console_scroll = ttk.Scrollbar(console_container, orient=tk.VERTICAL, command=self.console.yview)
        self.console.configure(yscrollcommand=self.console_scroll.set)
        self.console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.console_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._configure_console_tags()

        # Pane 2: Linked Messages Frame (Inspector)
        link_msg_pane = ttk.Frame(right_paned)
        right_paned.add(link_msg_pane, weight=1)
        ttk.Label(link_msg_pane, text="Linked Messages").pack(anchor=tk.W, pady=(0, 2))
        link_msg_container = ttk.Frame(link_msg_pane)
        link_msg_container.pack(fill=tk.BOTH, expand=True)
        self.link_msg_box = tk.Text(link_msg_container, state=tk.DISABLED, wrap=tk.WORD, height=6)
        self.link_msg_scroll = ttk.Scrollbar(link_msg_container, orient=tk.VERTICAL, command=self.link_msg_box.yview)
        self.link_msg_box.configure(yscrollcommand=self.link_msg_scroll.set)
        self.link_msg_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.link_msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Pane 3: Problems Frame
        problems_pane = ttk.Frame(right_paned)
        right_paned.add(problems_pane, weight=1)
        ttk.Label(problems_pane, text="Problems").pack(anchor=tk.W, pady=(0, 2))
        problems_container = ttk.Frame(problems_pane)
        problems_container.pack(fill=tk.BOTH, expand=True)
        self.problems = ttk.Treeview(
            problems_container,
            columns=("severity", "object", "script", "phase", "line", "message"),
            show="headings",
            height=4,
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
        self.problems_scroll = ttk.Scrollbar(problems_container, orient=tk.VERTICAL, command=self.problems.yview)
        self.problems.configure(yscrollcommand=self.problems_scroll.set)
        self.problems.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.problems_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.problems.bind("<Double-1>", self.open_selected_problem)

        status = ttk.Frame(self, relief=tk.SUNKEN)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(status, textvariable=self.status_var, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Label(status, textvariable=self.lines_var, width=18, anchor=tk.E).pack(side=tk.RIGHT, padx=6)
        ttk.Label(status, textvariable=self.fps_var, width=28, anchor=tk.E).pack(side=tk.RIGHT, padx=6)

    def _build_menu(self):
        menu = tk.Menu(self)
        self.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Project...", command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Project...", command=self.open_project, accelerator="Ctrl+O")
        self.recent_menu = tk.Menu(file_menu, tearoff=False)
        file_menu.add_cascade(label="Recent Projects", menu=self.recent_menu)
        self._update_recent_menu()
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Find...", command=self.find_text, accelerator="Ctrl+F")
        menu.add_cascade(label="Edit", menu=edit_menu)

        project_menu = tk.Menu(menu, tearoff=False)
        project_menu.add_command(label="Add Object...", command=self.add_object)
        project_menu.add_command(label="Add Script...", command=self.add_script)
        project_menu.add_command(label="Add Notecard...", command=self.add_notecard)
        project_menu.add_command(label="Object Settings...", command=self.open_object_settings)
        menu.add_cascade(label="Project", menu=project_menu)

        run_menu = tk.Menu(menu, tearoff=False)
        run_menu.add_command(label="Run", command=self.run_project, accelerator="F5")
        run_menu.add_command(label="Step", command=self.step_once, accelerator="F10")
        run_menu.add_command(label="Auto Tick", command=self.toggle_auto_tick)
        run_menu.add_command(label="Stop", command=self.stop_project, accelerator="Shift+F5")
        run_menu.add_command(label="Touch Selected Object", command=self.touch_selected_object)
        run_menu.add_command(label="Advanced Touch Selected...", command=self.open_advanced_touch)

        settings_menu = tk.Menu(menu, tearoff=False)
        settings_menu.add_command(label="World Settings...", command=self.open_world_settings)
        settings_menu.add_command(label="AI Settings...", command=self.open_ai_settings)
        menu.add_cascade(label="Settings", menu=settings_menu)

        console_menu = tk.Menu(menu, tearoff=False)
        console_menu.add_command(label="Clear Console", command=self.clear_console)
        menu.add_cascade(label="Console", menu=console_menu)

        self.bind_all("<Control-n>", lambda _event: self.new_project())
        self.bind_all("<Control-o>", lambda _event: self.open_project())
        self.bind_all("<Control-s>", lambda _event: self.save_project())
        self.bind_all("<F5>", lambda _event: self.run_project())
        self.bind_all("<F10>", lambda _event: self.step_once())
        self.bind_all("<Shift-F5>", lambda _event: self.stop_project())
        self.bind_all("<Control-f>", lambda _event: self.find_text())
        self.bind_all("<Control-F>", lambda _event: self.find_text())

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

    def selected_item(self):
        obj = self.selected_object()
        if not obj:
            return None
        idx = self.selected_script_index
        if 0 <= idx < len(obj.scripts):
            return obj.scripts[idx]
        nc_idx = idx - len(obj.scripts)
        if 0 <= nc_idx < len(obj.notecards):
            return obj.notecards[nc_idx]
        return None

    def _selected_script_line_count(self) -> int:
        item = self.selected_item()
        if not item:
            return 0
        if hasattr(item, "source"):
            return len(item.source.splitlines())
        else:
            return len(item.text.splitlines())

    def _update_line_status(self):
        self.lines_var.set(f"Lines: {self._selected_script_line_count()}")

    def _record_tick(self):
        self._fps_window_ticks += 1
        now = time.monotonic()
        elapsed = now - self._fps_window_start
        frame = self.runtime.loop.tick_count if self.runtime else 0
        if elapsed >= 1.0:
            self._last_fps = self._fps_window_ticks / elapsed
            self._fps_window_start = now
            self._fps_window_ticks = 0
        self.fps_var.set(f"Frame: {frame} | FPS: {self._last_fps:.1f}")

    def _reset_fps(self):
        self._fps_window_start = time.monotonic()
        self._fps_window_ticks = 0
        self._last_fps = 0.0
        self.fps_var.set("Frame: 0 | FPS: 0.0")

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
        for notecard in obj.notecards:
            self.script_list.insert(tk.END, notecard.name)
        total_items = len(obj.scripts) + len(obj.notecards)
        if total_items > 0:
            self.selected_script_index = min(self.selected_script_index, total_items - 1)
            self.script_list.selection_set(self.selected_script_index)

    def selected_object(self):
        if not self.project.objects:
            return None
        return self.project.objects[self.selected_object_index]

    def selected_script(self):
        obj = self.selected_object()
        if not obj or not obj.scripts:
            return None
        idx = self.selected_script_index
        if 0 <= idx < len(obj.scripts):
            return obj.scripts[idx]
        return None

    def save_current_editor(self):
        item = self.selected_item()
        if item:
            source = self.editor.get("1.0", tk.END).rstrip() + "\n"
            if hasattr(item, "source"):
                if source != item.source:
                    item.source = source
                    item.dirty = True
            else:
                if source != item.text:
                    item.text = source
                    item.dirty = True

    def _load_selected_script(self):
        self.project.sync_from_disk()
        item = self.selected_item()
        self.editor.delete("1.0", tk.END)
        if item:
            if hasattr(item, "source"):
                self.editor.insert("1.0", item.source)
            else:
                self.editor.insert("1.0", item.text)
        self.editor.edit_modified(False)
        self._update_line_status()

    def _replace_project(self, project: IdeProject, status: str):
        self._stop_auto_tick()
        self.project = project
        self.runtime = None
        self.selected_object_index = 0
        self.selected_script_index = 0
        self._dialog_signature = object()
        self._problems_signature = None
        self._reset_fps()
        self.clear_console()
        self._refresh_dialog_panel()
        self._clear_problems()
        self.title(f"LSL Developer - {self.project.folder}")
        self._refresh_lists()
        self._load_selected_script()
        self._set_status(status)
        self._add_to_recent(project.folder)

    def new_project(self):
        self._stop_auto_tick()
        parent = filedialog.askdirectory(initialdir=str(self.project.folder.parent), title="Choose Parent Folder")
        if not parent:
            return
        name = simpledialog.askstring("New Project", "Folder name:", initialvalue="lsl_project")
        if not name:
            return
        folder = Path(parent) / name
        project = IdeProject.blank(folder)
        project.save()
        self._replace_project(project, f"Created {project.folder}")

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
        self._stop_auto_tick()
        folder = filedialog.askdirectory(initialdir=str(self.project.folder))
        if folder:
            self.save_current_editor()
            self._replace_project(IdeProject.load(folder), f"Opened {folder}")

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
        self.project.sync_from_disk()
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

    def stop_project(self):
        self._stop_auto_tick()
        self.runtime = None
        self._refresh_dialog_panel()
        self._clear_problems()
        self._reset_fps()
        self.clear_console()
        self._set_status("Runtime stopped")
        self.append_console(ConsoleMessage("debug", "runtime stopped"))

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
        if hasattr(self, "link_msg_box"):
            self.link_msg_box.configure(state=tk.NORMAL)
            self.link_msg_box.delete("1.0", tk.END)
            self.link_msg_box.configure(state=tk.DISABLED)

    def append_console(self, message: ConsoleMessage):
        if message.message_type == "link_message":
            if hasattr(self, "link_msg_box"):
                self.link_msg_box.configure(state=tk.NORMAL)
                self.link_msg_box.insert(tk.END, f"{message.text}\n")
                self.link_msg_box.see(tk.END)
                self.link_msg_box.configure(state=tk.DISABLED)
            return

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

    def _add_to_recent(self, folder: Path):
        path_str = str(folder.resolve())
        recent = load_recent_projects()
        if path_str in recent:
            recent.remove(path_str)
        recent.insert(0, path_str)
        recent = recent[:10]
        save_recent_projects(recent)
        self._update_recent_menu()

    def _update_recent_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.delete(0, tk.END)
        recent = load_recent_projects()
        if not recent:
            self.recent_menu.add_command(label="(Empty)", state=tk.DISABLED)
            return
        for path_str in recent:
            path = Path(path_str)
            label = f"{path.name} ({path_str})"
            self.recent_menu.add_command(
                label=label,
                command=lambda p=path_str: self._open_recent(p)
            )

    def _open_recent(self, path_str: str):
        self._stop_auto_tick()
        folder = Path(path_str)
        if not folder.exists():
            messagebox.showerror("Error", f"Project folder not found:\n{path_str}")
            recent = load_recent_projects()
            if path_str in recent:
                recent.remove(path_str)
                save_recent_projects(recent)
                self._update_recent_menu()
            return
        self.save_current_editor()
        try:
            project = IdeProject.load(folder)
            self._replace_project(project, f"Opened {folder}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load project:\n{exc}")

    def find_text(self, _event=None):
        if hasattr(self, "_find_dialog") and self._find_dialog.winfo_exists():
            self._find_dialog.focus_set()
            return

        dialog = tk.Toplevel(self)
        self._find_dialog = dialog
        dialog.title("Find Text")
        dialog.transient(self)
        dialog.geometry("380x100")
        dialog.resizable(False, False)

        x = self.winfo_x() + (self.winfo_width() - 380) // 2
        y = self.winfo_y() + (self.winfo_height() - 100) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Find:").grid(row=0, column=0, sticky=tk.W, pady=5)
        search_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=search_var, width=30)
        entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        entry.focus_set()

        self.editor.tag_configure("search_highlight", background="yellow", foreground="black")

        def do_find():
            query = search_var.get()
            if not query:
                return
            start_index = self.editor.index(tk.INSERT)
            idx = self.editor.search(query, start_index, stopindex=tk.END, nocase=True)
            if not idx:
                idx = self.editor.search(query, "1.0", stopindex=start_index, nocase=True)
            if idx:
                self.editor.tag_remove("search_highlight", "1.0", tk.END)
                line, char = map(int, idx.split("."))
                end_idx = f"{line}.{char + len(query)}"
                self.editor.tag_add("search_highlight", idx, end_idx)
                self.editor.mark_set(tk.INSERT, end_idx)
                self.editor.see(idx)
            else:
                messagebox.showinfo("Find", f'Cannot find "{query}"', parent=dialog)

        def on_close():
            self.editor.tag_remove("search_highlight", "1.0", tk.END)
            dialog.destroy()

        btn_find = ttk.Button(frame, text="Find Next", command=do_find)
        btn_find.grid(row=1, column=1, sticky=tk.E, pady=5)

        btn_cancel = ttk.Button(frame, text="Cancel", command=on_close)
        btn_cancel.grid(row=1, column=2, sticky=tk.E, pady=5, padx=5)

        entry.bind("<Return>", lambda e: do_find())
        dialog.bind("<Escape>", lambda e: on_close())
        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def add_notecard(self):
        if not self.project.objects:
            self.project.add_object()
        self.save_current_editor()
        obj = self.selected_object()
        name = simpledialog.askstring("Add Notecard", "Notecard name:", initialvalue="config.nc")
        if not name:
            return
        if not name.endswith(".nc"):
            name = name + ".nc"
        for nc in obj.notecards:
            if nc.name == name:
                messagebox.showerror("Error", f"A notecard named '{name}' already exists.")
                return

        from ide.project import ProjectNotecard
        notecard = ProjectNotecard(name=name, text="", file=None, dirty=True)
        obj.notecards.append(notecard)
        self.project.save()

        self.selected_script_index = len(obj.scripts) + obj.notecards.index(notecard)
        self._refresh_script_list()
        self._load_selected_script()

    def open_object_settings(self):
        obj = self.selected_object()
        if not obj:
            messagebox.showinfo("Object Settings", "No object selected.")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"Object Settings - {obj.name}")
        dialog.transient(self)
        dialog.grab_set()

        dialog.geometry("450x540")
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 540) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Object Name:").grid(row=0, column=0, sticky=tk.W, pady=4)
        name_var = tk.StringVar(value=obj.name)
        ttk.Entry(frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky=tk.EW, pady=4)

        # Root Faces
        ttk.Label(frame, text="Root Faces:").grid(row=1, column=0, sticky=tk.W, pady=4)
        root_faces_var = tk.StringVar(value=str(getattr(obj, "num_faces", 6)))
        ttk.Spinbox(frame, from_=1, to=100, textvariable=root_faces_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=4)

        # Linked Prims CSV Description
        ttk.Label(frame, text="Linked Prims (CSV: Name, Faces):").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))

        csv_frame = ttk.Frame(frame)
        csv_frame.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW, pady=4)
        frame.rowconfigure(3, weight=1)
        frame.columnconfigure(1, weight=1)

        csv_text = tk.Text(csv_frame, height=10, width=40, wrap=tk.NONE)
        v_scroll = ttk.Scrollbar(csv_frame, orient=tk.VERTICAL, command=csv_text.yview)
        h_scroll = ttk.Scrollbar(csv_frame, orient=tk.HORIZONTAL, command=csv_text.xview)
        csv_text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        csv_text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        csv_frame.rowconfigure(0, weight=1)
        csv_frame.columnconfigure(0, weight=1)

        # Populate CSV
        csv_lines = []
        for lp in getattr(obj, "linked_prims", []):
            csv_lines.append(f"{lp.get('name', '')}, {lp.get('num_faces', 6)}")
        csv_text.insert("1.0", "\n".join(csv_lines))

        # Easy Mode Helper
        easy_frame = ttk.LabelFrame(frame, text="Easy Mode Generator (Replace)", padding=8)
        easy_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=8)

        ttk.Label(easy_frame, text="Add").grid(row=0, column=0, sticky=tk.W, padx=2)
        easy_count_var = tk.StringVar(value="24")
        ttk.Entry(easy_frame, textvariable=easy_count_var, width=5).grid(row=0, column=1, sticky=tk.W, padx=2)
        ttk.Label(easy_frame, text="linked objects, with").grid(row=0, column=2, sticky=tk.W, padx=2)
        easy_faces_var = tk.StringVar(value="8")
        ttk.Entry(easy_frame, textvariable=easy_faces_var, width=5).grid(row=0, column=3, sticky=tk.W, padx=2)
        ttk.Label(easy_frame, text="faces each").grid(row=0, column=4, sticky=tk.W, padx=2)

        def easy_generate():
            try:
                count = int(easy_count_var.get())
                faces = int(easy_faces_var.get())
                if count < 0 or faces < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Count must be non-negative and faces must be >= 1.", parent=dialog)
                return

            new_lines = []
            base_name = name_var.get().strip() or "Object 1"
            for idx in range(count):
                new_lines.append(f"{base_name} Link {idx + 2}, {faces}")

            csv_text.delete("1.0", tk.END)
            csv_text.insert("1.0", "\n".join(new_lines))

        ttk.Button(easy_frame, text="Generate", command=easy_generate).grid(row=0, column=5, sticky=tk.E, padx=10)

        # Save/Cancel
        def save():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Object name cannot be empty.", parent=dialog)
                return

            for other in self.project.objects:
                if other is not obj and other.name == new_name:
                    messagebox.showerror("Error", f"An object named '{new_name}' already exists.", parent=dialog)
                    return

            try:
                new_root_faces = int(root_faces_var.get())
                if new_root_faces < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Root Faces must be a positive integer.", parent=dialog)
                return

            # Parse CSV
            new_linked = []
            for line in csv_text.get("1.0", tk.END).splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",", 1)
                p_name = parts[0].strip()
                p_faces = 6
                if len(parts) > 1:
                    try:
                        p_faces = int(parts[1].strip())
                        if p_faces < 1:
                            p_faces = 6
                    except ValueError:
                        pass
                if not p_name:
                    p_name = f"{new_name} Link {len(new_linked) + 2}"
                new_linked.append({"name": p_name, "num_faces": p_faces})

            obj.name = new_name
            obj.num_faces = new_root_faces
            obj.linked_prims = new_linked

            self.project.save()
            self._refresh_lists()
            self._set_status(f"Updated settings for object '{new_name}'")
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side=tk.RIGHT)

    def open_advanced_touch(self):
        obj = self.selected_object()
        if not obj:
            messagebox.showinfo("Advanced Touch", "No object selected.")
            return

        if not self.runtime:
            self.run_project()
        if not self.runtime:
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"Advanced Touch - {obj.name}")
        dialog.transient(self)
        dialog.grab_set()

        dialog.geometry("380x280")
        x = self.winfo_x() + (self.winfo_width() - 380) // 2
        y = self.winfo_y() + (self.winfo_height() - 280) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        total_prims = 1 + len(getattr(obj, "linked_prims", []))

        # Link Number
        ttk.Label(frame, text="Link Number (0 for single prim, or 1 to N):").grid(row=0, column=0, sticky=tk.W, pady=6)
        link_num_var = tk.StringVar(value="1")
        link_spin = ttk.Spinbox(frame, from_=0, to=total_prims, textvariable=link_num_var, width=10)
        link_spin.grid(row=0, column=1, sticky=tk.W, pady=6)

        # Face count label
        face_limit_label = ttk.Label(frame, text="Valid faces: 0 to 5 (or -1 for all)", font=("", 9, "italic"))
        face_limit_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))

        def update_face_limit(*args):
            try:
                ln = int(link_num_var.get())
            except ValueError:
                return
            if ln <= 1:
                faces = getattr(obj, "num_faces", 6)
            elif 2 <= ln <= len(obj.linked_prims) + 1:
                faces = obj.linked_prims[ln - 2].get("num_faces", 6)
            else:
                faces = 6
            face_limit_label.configure(text=f"Valid faces: 0 to {faces - 1} (or -1 for all)")

        link_num_var.trace_add("write", update_face_limit)
        update_face_limit()

        # Touch Face
        ttk.Label(frame, text="Touch Face (-1 for all):").grid(row=2, column=0, sticky=tk.W, pady=6)
        face_var = tk.StringVar(value="-1")
        ttk.Entry(frame, textvariable=face_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=6)

        # Touch UV coordinates
        ttk.Label(frame, text="Touch U (0.0 to 1.0):").grid(row=3, column=0, sticky=tk.W, pady=6)
        u_var = tk.StringVar(value="0.5")
        ttk.Entry(frame, textvariable=u_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=6)

        ttk.Label(frame, text="Touch V (0.0 to 1.0):").grid(row=4, column=0, sticky=tk.W, pady=6)
        v_var = tk.StringVar(value="0.5")
        ttk.Entry(frame, textvariable=v_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=6)

        def do_touch():
            try:
                ln = int(link_num_var.get())
                face = int(face_var.get())
                u = float(u_var.get())
                v = float(v_var.get())
                if not (0.0 <= u <= 1.0) or not (0.0 <= v <= 1.0):
                    raise ValueError("UV coordinates must be between 0.0 and 1.0.")
            except ValueError as exc:
                messagebox.showerror("Error", f"Invalid input: {exc}", parent=dialog)
                return

            if self.runtime:
                from core.types import LSLVector
                self.runtime.touch(obj.name, link_num=ln, face=face, uv=LSLVector(u, v, 0.0))
                if self.auto_tick:
                    self._set_status(f"Touched {obj.name} (Link {ln}, Face {face}, UV <{u:.2f},{v:.2f}>)")
                else:
                    self.step_once()
                dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(buttons, text="Touch!", command=do_touch).pack(side=tk.RIGHT)

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
