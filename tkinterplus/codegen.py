"""Readable Tkinter-style Python; property strings remain safe literals."""
from .project import Project

NAMES = {"Textbox": "Text", "CheckBox": "Checkbutton", "RadioButton": "Radiobutton",
         "SpinBox": "Spinbox", "Slider": "Scale", "ComboBox": "Combobox", "ProgressBar": "Progressbar"}


def widget_arguments(item):
    props = dict(item.props)
    colors = props.pop("colors", {}).copy()
    args = {}
    if "text" in props:
        args["text"] = props.pop("text")
    if item.kind == "Label":
        size, weight = props.pop("font_size"), props.pop("weight")
        if size != 11 or weight != "normal":
            args["font"] = ("Segoe UI", size, weight)
    if item.kind == "Button":
        size = props.pop("font_size")
        if size != 10:
            args["font"] = ("Segoe UI", size)
    background = "accent" if item.kind == "Button" and props.get("variant") == "primary" else (
        "danger" if item.kind == "Button" and props.get("variant") == "danger" else
        "surface" if item.kind in ("Button", "Entry", "Textbox", "ComboBox", "SpinBox") else "background")
    if background in colors:
        args["bg"] = colors.pop(background)
    if "text" in colors:
        args["fg"] = colors.pop("text")
    defaults = {"state": "readonly" if item.kind == "ComboBox" else "normal", "show": "", "muted": False,
                "anchor": "w", "radius": 5, "variant": "primary" if item.kind == "Button" else "surface",
                "selected": False, "from_": 0, "to": 100, "increment": 1}
    for key, value in props.items():
        if key in defaults and value == defaults[key]:
            continue
        if key == "options":
            key = "values"
        if key == "value" and item.kind in ("Entry", "Textbox"):
            continue
        args[key] = value
    if colors:
        args["colors"] = colors
    return args


def generate_python(project, style="simple"):
    project = Project.from_dict(project.to_dict())
    if style not in ("simple", "function"):
        raise ValueError("Code style must be simple or function")
    lines = ["import tkinterplus as ui", ""]
    indent = "    " if style == "function" else ""
    if style == "function":
        lines += ["", "def build_app():"]
    options = []
    if project.theme != "dark":
        options.append(f"theme={project.theme!r}")
    if project.colors:
        options.append(f"colors={project.colors!r}")
    body = [f"root = ui.Tk({', '.join(options)})", f"root.title({project.title!r})",
            f"root.geometry('{project.width}x{project.height}')", "root.resizable(False, False)", ""]
    if style == "function":
        body.insert(4, "root.widgets = {}")
    used = {"root", "ui"}
    for item in project.widgets:
        variable = item.id
        suffix = 1
        while variable in used:
            variable = f"{item.id}_{suffix}"
            suffix += 1
        used.add(variable)
        args = widget_arguments(item)
        state = args.pop("state", None) if item.kind in ("Entry", "Textbox") else None
        arguments = ", ".join(f"{key}={value!r}" for key, value in args.items())
        body.append(f"{variable} = ui.{NAMES.get(item.kind, item.kind)}(root{', ' if arguments else ''}{arguments})")
        if item.kind in ("Entry", "Textbox") and item.props["value"]:
            body.append(f"{variable}.insert({'0' if item.kind == 'Entry' else repr('1.0')}, {item.props['value']!r})")
        if state:
            body.append(f"{variable}.configure(state={state!r})")
        body.append(f"{variable}.place(x={item.x}, y={item.y}, width={item.width}, height={item.height})")
        if style == "function":
            body.append(f"root.widgets[{item.id!r}] = {variable}")
        body.append("")
    if style == "function":
        body += ["return root"]
        lines += [indent+line if line else "" for line in body]
        lines += ["", "", 'if __name__ == "__main__":', "    build_app().mainloop()", ""]
    else:
        lines += body + ['if __name__ == "__main__":', "    root.mainloop()", ""]
    return "\n".join(lines)
