"""Run from the repository root: python -m examples.demo"""
from tkinterplus.codegen import generate_python
from tkinterplus.project import demo_project


def main():
    # Build from the generated source to exercise the same export path as the editor.
    namespace = {"__name__": "tkinterplus_demo"}
    exec(compile(generate_python(demo_project()), "demo_generated.py", "exec"), namespace)
    namespace["root"].mainloop()


if __name__ == "__main__":
    main()
