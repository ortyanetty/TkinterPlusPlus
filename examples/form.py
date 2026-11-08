"""Form with values, callbacks and a custom palette: python -m examples.form."""
import tkinterplus as ui


def build_app():
    app = ui.App(title="Параметры подключения", width=520, height=440, theme="light",
                 colors={"accent": (47, 105, 218), "hover": "#2057bd"})
    app.columnconfigure(0, weight=1)
    ui.Label(app, text="Параметры подключения", font_size=18, weight="bold").grid(
        row=0, column=0, sticky="w", padx=28, pady=(24, 20))
    ui.Label(app, text="Имя пользователя").grid(row=1, column=0, sticky="w", padx=28)
    name = ui.Entry(app)
    name.grid(row=2, column=0, sticky="ew", padx=28, pady=(8, 16))
    ui.Label(app, text="Сервер").grid(row=3, column=0, sticky="w", padx=28)
    server = ui.ComboBox(app, options=["Локальный", "Рабочий", "Тестовый"])
    server.grid(row=4, column=0, sticky="ew", padx=28, pady=(8, 16))
    remember = ui.CheckBox(app, text="Запомнить параметры", value=True)
    remember.grid(row=5, column=0, sticky="w", padx=28)
    status = ui.Label(app, text="", muted=True)
    status.grid(row=7, column=0, sticky="w", padx=28, pady=12)

    def save():
        status.configure(text=f"{name.get().strip()} · {server.get()}" if name.get().strip() else "Введите имя пользователя")

    button = ui.Button(app, text="Сохранить", command=save)
    button.grid(row=6, column=0, sticky="w", padx=28, pady=(20, 0))
    app.widgets = dict(name=name, server=server, remember=remember, status=status, save=button)
    return app


if __name__ == "__main__":
    build_app().mainloop()
