import tkinterplus as ui

root = ui.Tk()
root.title('Параметры проекта')
root.geometry('760x560')
root.resizable(False, False)

label_1 = ui.Label(root, text='Параметры проекта', font=('Segoe UI', 14, 'bold'))
label_1.place(x=40, y=28, width=660, height=28)

label_2 = ui.Label(root, text='Общие настройки', font=('Segoe UI', 12, 'bold'))
label_2.place(x=40, y=70, width=660, height=36)

label_3 = ui.Label(root, text='Конфигурация приложения', font=('Segoe UI', 12, 'normal'), muted=True)
label_3.place(x=40, y=126, width=660, height=30)

separator_1 = ui.Separator(root)
separator_1.place(x=40, y=176, width=680, height=2)

label_4 = ui.Label(root, text='Название проекта', font=('Segoe UI', 12, 'bold'))
label_4.place(x=40, y=200, width=300, height=28)

entry_1 = ui.Entry(root)
entry_1.insert(0, 'Project1')
entry_1.place(x=40, y=236, width=320, height=42)

label_5 = ui.Label(root, text='Рабочая среда', font=('Segoe UI', 12, 'bold'))
label_5.place(x=400, y=200, width=300, height=28)

combobox_1 = ui.Combobox(root, values=['Разработка', 'Дизайн', 'Личный проект'], value='Разработка')
combobox_1.place(x=400, y=236, width=320, height=42)

switch_1 = ui.Switch(root, text='Получать уведомления', value=True)
switch_1.place(x=40, y=305, width=300, height=36)

checkbox_1 = ui.Checkbutton(root, text='Сохранять настройки', value=True)
checkbox_1.place(x=400, y=305, width=300, height=36)

label_6 = ui.Label(root, text='Прогресс', font=('Segoe UI', 12, 'normal'), muted=True)
label_6.place(x=40, y=370, width=300, height=28)

progressbar_1 = ui.Progressbar(root, value=75)
progressbar_1.place(x=40, y=410, width=680, height=12)

button_1 = ui.Button(root, text='Применить')
button_1.place(x=40, y=470, width=210, height=44)

button_2 = ui.Button(root, text='Отмена', variant='secondary')
button_2.place(x=270, y=470, width=160, height=44)

if __name__ == "__main__":
    root.mainloop()
