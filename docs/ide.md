# Tk IDE

The first IDE slice is a Tk application over the existing offline simulator.

Run it with:

```bash
./ide.sh path/to/project-folder
```

A project is just a folder containing `project.json`. The JSON stores objects
and their script sources. All projects currently use the same seeded background
world: one offline region, one parcel, demo owner/visitor avatars, and the
project's scripted objects.

Current IDE behavior:

- Traditional menu bar plus the top action toolbar.
- Add multiple objects.
- Add multiple scripts inside each object.
- Save/load notecard contents inside objects.
- Edit script source.
- Save/load the project data folder.
- Run all scripts in the same seeded simulator.
- Step the simulator manually.
- Auto tick the simulator.
- Touch the selected object.
- Send avatar chat input from the console panel on a chosen channel.
- Respond to the latest simulated `llDialog` from the dialog strip above the console.
- Render tagged console output for owner say, chat, debug, stub warnings, and errors.
- Collect compile/runtime diagnostics without aborting the whole project.
- Show diagnostics in a Problems panel with object, script, phase, location, and message.
- Select a seeded world avatar profile from Settings -> World Settings.
- Show status for runtime state, measured tick FPS, and selected script line count.
- Configure OpenAI API key/model from Settings -> AI Settings.
- Ask the AI questions about the project scripts and let it replace project script source.

New project folders are seeded with a small multi-object test scene. The
`Control Panel` object includes simulator/API scripts plus `language_probe.lsl`,
which exercises loops, conditions, functions, lists, casts, variables, and state
transitions as part of the normal test suite. It also includes
`environment_probe.lsl`, which checks API, IO, region/parcel/avatar state,
inventory, object details, primitive params, linkset data, parcel media, object
position, and persistence-style reads after writes. The project also stores a
nested inventory object and `rez_probe.lsl` rezzes it, verifies `object_rez`,
and proves the child object's own script starts. `sensor_probe.lsl` checks
avatar sensors, object sensors, name filters, `no_sensor`, repeated sensors,
`llSensorRemove`, and detected accessors.

World profiles are stored in `project.json` as `world_profile`:

- `none`: 0 avatars
- `one`: 1 avatar
- `couple`: 2 avatars
- `dozens`: 24 avatars
- `sixty_plus`: 64 avatars

When a script fails to compile, the IDE records a diagnostic, disables that
script, and continues running the rest of the project. Runtime errors during
events are handled the same way. Double-clicking a row in Problems opens the
matching script and moves the editor cursor to the reported line when available.

The IDE intentionally does not render a 3D world. Script-visible object, prim,
parcel, chat, dialogs, linkset data, inventory/notecards, and stored effect
state are handled by the simulator model.

The launcher uses `.venv/bin/python` when that venv already exists. To create it
first, run:

```bash
./ide.sh --init-venv path/to/project-folder
```

The app has no third-party runtime dependencies yet, so a system Python with Tk
available is enough for now.

AI settings are stored outside project folders in
`~/.config/lsldeveloper/settings.json`. The API key can also come from
`OPENAI_API_KEY`. AI edits are currently scoped to LSL scripts stored in the
project; the assistant is not allowed to edit the Python simulator or IDE code
from inside the Tk application.
