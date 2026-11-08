"""Minimal button example: python -m examples.button."""
import tkinterplus as ui


def build_app():
    app = ui.App(title="Кнопка · Tkinter++", width=420, height=240, theme="light")
    status = ui.Label(app, text="Ожидание нажатия")
    status.pack(pady=(36, 20))
    button = ui.Button(app, text="Нажать", width=180, height=40,
                       command=lambda: status.configure(text="Кнопка нажата"))
    button.pack()
    app.widgets = {"status": status, "button": button}
    return app


if __name__ == "__main__":
    build_app().mainloop()
