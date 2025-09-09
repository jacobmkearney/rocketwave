import sys
import argparse
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
    QFileDialog,
)
import pyqtgraph as pg
from pythonosc import dispatcher, osc_server


class OSCDataPlotter:
    def __init__(self, ip: str = '127.0.0.1', port: int = 7000):
        self.ip = ip
        self.port = port

        # address -> deque[(ts, [args...])]
        self.buffers: Dict[str, Deque[Tuple[datetime, Tuple[float, ...]]]] = defaultdict(lambda: deque(maxlen=10000))
        self.addresses: List[str] = []
        self.current_address: str = ''

        # OSC server
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map('*', self._on_any)
        self.server = osc_server.ThreadingOSCUDPServer((self.ip, self.port), self.dispatcher)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        # UI setup
        self.window = QWidget()
        self.window.setWindowTitle('RocketWave OSC Visualizer')
        self.layout = QVBoxLayout(self.window)

        self.ctrl_widget = QWidget()
        self.ctrl_layout = QHBoxLayout(self.ctrl_widget)
        self.layout.addWidget(self.ctrl_widget)

        self.stream_box = QComboBox()
        self.stream_box.activated.connect(self._on_stream_change)
        self.ctrl_layout.addWidget(self.stream_box)

        self.time_range_label = QLabel('Time Range (s):')
        self.ctrl_layout.addWidget(self.time_range_label)
        self.time_range_spin = QDoubleSpinBox()
        self.time_range_spin.setRange(1, 3600)
        self.time_range_spin.setValue(15)
        self.time_range_spin.setSingleStep(1)
        self.ctrl_layout.addWidget(self.time_range_spin)

        self.save_button = QPushButton('Save Data')
        self.save_button.clicked.connect(self._on_save)
        self.ctrl_layout.addWidget(self.save_button)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.layout.addWidget(self.scroll)

        self.plots_container = QWidget()
        self.plots_layout = QVBoxLayout(self.plots_container)
        self.scroll.setWidget(self.plots_container)

        self.plots: List[pg.PlotWidget] = []
        self.curves: List[pg.PlotDataItem] = []

        # Timers
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_plot)
        self.timer.timeout.connect(self._update_stream_box)
        self.timer.start(100)

        self.window.show()

    # OSC handler
    def _on_any(self, address: str, *args):
        now = datetime.now()
        if address not in self.addresses:
            self.addresses.append(address)
        # Store tuple of args (floats)
        try:
            vals = tuple(float(a) for a in args)
        except Exception:
            # If non-float payload, skip plotting but keep address in list
            return
        self.buffers[address].append((now, vals))

    # UI callbacks
    def _on_stream_change(self, index: int):
        if index < 0:
            return
        self.current_address = self.stream_box.itemText(index)
        # Clear old plots
        for plot in self.plots:
            plot.close()
            self.plots_layout.removeWidget(plot)
        self.plots = []
        self.curves = []

        # Determine dimensionality from the most recent sample
        buf = self.buffers.get(self.current_address, deque())
        num_values = len(buf[-1][1]) if len(buf) > 0 else 1
        # Choose per-channel labels. For /muse/eeg use TP9, AF7, AF8, TP10.
        labels = [f"value[{k}]" for k in range(num_values)]
        if self.current_address == '/muse/eeg':
            muse_labels = ['TP9', 'AF7', 'AF8', 'TP10']
            labels = [muse_labels[k] if k < len(muse_labels) else f"value[{k}]" for k in range(num_values)]
        for i in range(num_values):
            title = f"{self.current_address} — {labels[i]}"
            plot = pg.PlotWidget(title=title)
            plot.setLabel('bottom', 'Time (s)')
            plot.setLabel('left', 'Value')
            curve = plot.plot(pen=pg.mkPen(pg.intColor(i, 10)))
            self.plots.append(plot)
            self.curves.append(curve)
            self.plots_layout.addWidget(plot)

    def _on_save(self):
        if not self.current_address:
            return
        buf = list(self.buffers.get(self.current_address, []))
        if not buf:
            return
        save_path, _ = QFileDialog.getSaveFileName(None, 'Save Data', '', 'CSV Files (*.csv);;All Files (*)')
        if not save_path:
            return
        with open(save_path, 'w') as f:
            for ts, args in buf:
                row = [ts.isoformat(), self.current_address] + [str(v) for v in args]
                f.write(','.join(row) + '\n')

    # Periodic updates
    def _update_stream_box(self):
        existing = {self.stream_box.itemText(i) for i in range(self.stream_box.count())}
        for addr in sorted(self.addresses):
            if addr not in existing:
                self.stream_box.addItem(addr)
        if not self.current_address and self.stream_box.count() > 0:
            self._on_stream_change(0)

    def _update_plot(self):
        if not self.current_address:
            return
        buf = list(self.buffers.get(self.current_address, []))
        if not buf:
            return
        # Filter by time range
        now = datetime.now()
        horizon = now - timedelta(seconds=float(self.time_range_spin.value()))
        buf = [(ts, vals) for (ts, vals) in buf if ts >= horizon]
        if not buf:
            return

        t0 = buf[0][0]
        xs = [(ts - t0).total_seconds() for (ts, _) in buf]
        num_vals = len(buf[-1][1])
        # Ensure plots match dimensionality
        if len(self.plots) != num_vals:
            self._on_stream_change(self.stream_box.currentIndex())
        for i in range(num_vals):
            ys = [vals[i] if i < len(vals) else 0.0 for (_, vals) in buf]
            if i < len(self.curves):
                self.curves[i].setData(xs, ys)


def main():
    parser = argparse.ArgumentParser(description='OSC visualizer for Muse endpoints')
    parser.add_argument('--ip', default='127.0.0.1', help='IP to bind (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=7000, help='OSC listen port (default: 7000)')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    plotter = OSCDataPlotter(ip=args.ip, port=args.port)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()


