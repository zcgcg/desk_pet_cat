"""全形态切换演示：轮流展示四种状态皮肤 + 台词气泡，展示完自动退出。

用法：python demo_skins.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import main as cat

STATES = [
    cat.PetState.IDLE,
    cat.PetState.WORKING,
    cat.PetState.ALERT,
    cat.PetState.FOLLOWING,
]
INTERVAL_MS = 3500


def main():
    app = QApplication(sys.argv)
    pet = cat.Cat()
    pet._sense_timer.stop()  # 演示期间锁定状态，不被心跳感知打断
    pet.show()

    index = {"i": 0}

    def next_state():
        st = STATES[index["i"] % len(STATES)]
        pet.set_state(st)
        print("demo state:", st.value, "->", pet._bubble.text())
        index["i"] += 1
        if index["i"] > len(STATES):
            app.quit()

    timer = QTimer()
    timer.timeout.connect(next_state)
    timer.start(INTERVAL_MS)
    next_state()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
