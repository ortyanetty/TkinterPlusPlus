"""Interactive widget gallery: python -m examples.gallery."""
import tkinterplus as ui


def build_app(theme="dark"):
    app = ui.App(title="Tkinter++ · Виджеты библиотеки", width=920, height=700, theme=theme)
    app.minsize(840, 660)
    header = ui.Frame(app, variant="background")
    header.pack(fill="x", padx=28, pady=(24, 20))
    ui.Label(header, text="Виджеты библиотеки", font_size=20, weight="bold").pack(side="left")
    ui.Button(header, text="Светлая", variant="secondary", width=96,
              command=lambda: app.set_theme("light")).pack(side="right", padx=(8, 0))
    ui.Button(header, text="Тёмная", variant="secondary", width=96,
              command=lambda: app.set_theme("dark")).pack(side="right")
    body = ui.Frame(app, variant="background")
    body.pack(fill="both", expand=True, padx=28, pady=(0, 24))
    body.columnconfigure((0, 1), weight=1, uniform="column")
    body.rowconfigure(0, weight=1)
    left, right = ui.Frame(body), ui.Frame(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def title(parent, text):
        ui.Label(parent, text=text, font_size=12, weight="bold").pack(anchor="w", padx=20, pady=(20, 12))

    title(left, "Поля ввода")
    ui.Label(left, text="Имя проекта", muted=True).pack(anchor="w", padx=20, pady=(0, 6))
    ui.Entry(left, value="Project1").pack(fill="x", padx=20)
    ui.Label(left, text="Среда", muted=True).pack(anchor="w", padx=20, pady=(16, 6))
    ui.ComboBox(left, options=["Разработка", "Тестирование", "Публикация"]).pack(fill="x", padx=20)
    ui.Label(left, text="Число потоков", muted=True).pack(anchor="w", padx=20, pady=(16, 6))
    ui.SpinBox(left, value=8, from_=1, to=64).pack(fill="x", padx=20)
    ui.Label(left, text="Описание", muted=True).pack(anchor="w", padx=20, pady=(16, 6))
    ui.Textbox(left, value="Приложение на Python и Tkinter++", height=4).pack(fill="x", padx=20)
    ui.Label(left, text="Недоступное поле", muted=True).pack(anchor="w", padx=20, pady=(16, 6))
    ui.Entry(left, value="Только для чтения", state="disabled").pack(fill="x", padx=20)
    title(right, "Параметры")
    ui.CheckBox(right, text="Сохранять автоматически", value=True).pack(anchor="w", padx=20)
    ui.CheckBox(right, text="Открыть после экспорта").pack(anchor="w", padx=20, pady=(4, 8))
    ui.Switch(right, text="Уведомления", value=True).pack(anchor="w", padx=20)
    ui.RadioButton(right, text="Локальный проект", group="project", value="local", selected=True).pack(anchor="w", padx=20, pady=(12, 0))
    ui.RadioButton(right, text="Общий проект", group="project", value="shared").pack(anchor="w", padx=20)
    ui.Separator(right).pack(fill="x", padx=20, pady=18)
    progress = ui.ProgressBar(right, value=65)
    ui.Label(right, text="Масштаб / прогресс", muted=True).pack(anchor="w", padx=20)
    ui.Slider(right, value=65, command=lambda v: progress.configure(value=float(v))).pack(fill="x", padx=20, pady=10)
    progress.pack(fill="x", padx=20, ipady=2)
    buttons = ui.Frame(right)
    buttons.pack(fill="x", padx=20, pady=(24, 12))
    ui.Button(buttons, text="Применить", width=150).pack(side="left")
    ui.Button(buttons, text="Отмена", variant="secondary", width=130).pack(side="left", padx=(10, 0))
    ui.Button(right, text="Собственный цвет · HEX / RGB", width=300,
              colors={"accent": (113, 77, 196), "hover": "#835fd6"}).pack(anchor="w", padx=20)
    return app


if __name__ == "__main__":
    build_app().mainloop()
