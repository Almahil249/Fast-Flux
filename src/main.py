import sys
import os
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

# Add project root to sys.path to allow running as script
if getattr(sys, 'frozen', False):
    # If running as an executable (PyInstaller)
    project_root = sys._MEIPASS
else:
    # If running as a script
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Ensure the root of the project (containing 'src') is in sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set environment variable for bundled resources
os.environ["FF_RESOURCE_DIR"] = project_root

from src.ui.main_window import MainWindow

def main():
    # Fix for Windows Taskbar Icon
    if os.name == 'nt':
        import ctypes
        myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
