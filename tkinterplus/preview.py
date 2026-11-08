"""Run the real Tkinter preview in a process separate from the Qt editor."""
import sys
from .project import MAX_FILE_BYTES, Project, create_widget
from .widgets import App


def build_preview(project):
    project = Project.from_dict(project.to_dict())
    app = App(title=project.title, width=project.width, height=project.height, theme=project.theme, colors=project.colors)
    app.resizable(False, False)
    for item in project.widgets:
        create_widget(app, item)
    return app


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments:
        if len(arguments) != 1:
            raise ValueError("Expected one project JSON path")
        project = Project.load(arguments[0])
    else:
        data = sys.stdin.buffer.read(MAX_FILE_BYTES+1)
        project = Project.loads(data.decode("utf-8"))
    build_preview(project).mainloop()


if __name__ == "__main__":
    main()
