"""A complete Tkinter-style program: python -m examples.simple_button."""
import tkinterplus as ui

root = ui.Tk()
root.title("Моя программа")
root.geometry("420x240")

label = ui.Label(root, text="Ожидание нажатия")
label.pack(pady=30)

def click():
    label.configure(text="Кнопка нажата")

button = ui.Button(root, text="Нажать", bg="#2563eb", fg="white", command=click)
button.pack()

if __name__ == "__main__":
    root.mainloop()
