"""Run the real Tkinter preview in a process separate from the Qt editor."""
import sys
from .project import MAX_FILE_BYTES, Project, create_widget
from .widgets import App


def build_preview(project):
    project = Project.from_dict(project.to_dict())
    app = App(title=project.title, width=project.width, height=project.height, theme=project.theme)
    app.resizable(False, False)
    app.configure(background=app.colors.surface)
    for item in project.widgets:
        create_widget(app, item)
    return app


def main():
    data = sys.stdin.buffer.read(MAX_FILE_BYTES+1)
    project = Project.loads(data.decode("utf-8"))
    build_preview(project).mainloop()


if __name__ == "__main__":
    main()
