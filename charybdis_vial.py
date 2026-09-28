# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys

# Ensure MINGW64 Qt DLLs are discoverable
mingw_bin = r"C:\QMK_MSYS\mingw64\bin"
if os.path.exists(mingw_bin):
    os.environ["PATH"] = mingw_bin + ";" + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(mingw_bin)
        except Exception:
            pass

# Ensure correct path
base_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(base_dir, "src", "main", "python")
resources_dir = os.path.join(base_dir, "src", "main", "resources", "base")

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Patch hidapi adapter for pyhidapi
import hid

class DeviceAdapter:
    def __init__(self):
        self._dev = None

    def open_path(self, path):
        self._dev = hid.Device(path=path)

    def write(self, data):
        return self._dev.write(bytes(data))

    def read(self, max_length, timeout_ms=None):
        if timeout_ms is not None:
            return list(self._dev.read(max_length, timeout=timeout_ms))
        return list(self._dev.read(max_length))

    def close(self):
        if self._dev:
            self._dev.close()
            self._dev = None

hid.device = DeviceAdapter

from PyQt5 import QtWidgets, QtGui, QtCore

class CharybdisVialContext:
    def __init__(self):
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("Charybdis Vial")
        self.build_settings = {
            "app_name": "Charybdis Vial",
            "version": "1.0.0"
        }
        # Set dark theme palette
        self.app.setStyle("Fusion")
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(22, 22, 22))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 30))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 45))
        palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
        palette.setColor(QtGui.QPalette.Link, QtGui.QColor(88, 166, 255))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(88, 166, 255))
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
        self.app.setPalette(palette)

    def get_resource(self, name):
        p = os.path.join(resources_dir, name)
        if os.path.exists(p):
            return p
        return os.path.join(base_dir, name)

def main():
    appctx = CharybdisVialContext()
    from main_window import MainWindow
    window = MainWindow(appctx)
    window.setWindowTitle("Charybdis Vial - Custom Studio")
    window.show()
    sys.exit(appctx.app.exec_())

if __name__ == "__main__":
    main()
