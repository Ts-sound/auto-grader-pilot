"""拖框取坐标：python scripts/region_picker.py
窗口出现后按住左键拖出一个矩形，松手即打印 region YAML，Esc 退出。
看的是物理像素（已开 DPI 感知），可直接粘进 config.yaml。
"""

from __future__ import annotations

import sys
import tkinter as tk

from agp import capture


def main() -> int:
    capture.init_dpi()
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.25)
    root.attributes("-topmost", True)
    canvas = tk.Canvas(root, cursor="cross", bg="grey")
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        40, 40, anchor="nw", fill="yellow", font=("Consolas", 20),
        text="拖拽框选区域 → 松手打印坐标；Esc 退出",
    )
    state = {"x0": 0, "y0": 0, "rect": None}

    def on_press(e):
        state["x0"], state["y0"] = e.x, e.y
        if state["rect"]:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=3)

    def on_drag(e):
        if state["rect"]:
            canvas.coords(state["rect"], state["x0"], state["y0"], e.x, e.y)

    def on_release(e):
        left, top = min(state["x0"], e.x), min(state["y0"], e.y)
        width, height = abs(e.x - state["x0"]), abs(e.y - state["y0"])
        print(f"  region: {{left: {left}, top: {top}, width: {width}, height: {height}}}", flush=True)

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", lambda _e: root.destroy())
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
