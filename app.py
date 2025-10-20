import json
import logging
import os
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, QLibraryInfo, pyqtSignal, QTimer
import asyncio
import importlib
import time


CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        return {"cell_number": "", "factory": "", "cell_leader": ""}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"cell_number": "", "factory": "", "cell_leader": ""}


def save_config(data: dict):
    ensure_config_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Takt-Time Process Tracker")
        self._analysis_running = False
        self._worker_thread = None

        # Estado da tela Takt e timeout
        self.takt_screen_working = False
        self.last_takt_screen_check = None
        self.takt_timeout_sec = 6
        self.last_takt_time_count = 0

        self._build_ui()
        self._load()

        # Timer para verificar periodicamente o status
        self._takt_timer = QTimer(self)
        self._takt_timer.setInterval(1000)  # checa a cada 1s
        self._takt_timer.timeout.connect(self._check_takt_screen_status)
        self._takt_timer.start()

    def _build_ui(self):
        layout = QVBoxLayout()

        # Configuração de inputs
        form_layout = QVBoxLayout()

        self.cell_input = QLineEdit()
        self.factory_input = QLineEdit()
        self.leader_input = QLineEdit()

        form_layout.addWidget(QLabel("Número da célula:"))
        form_layout.addWidget(self.cell_input)
        form_layout.addWidget(QLabel("Fábrica:"))
        form_layout.addWidget(self.factory_input)
        form_layout.addWidget(QLabel("Líder da célula:"))
        form_layout.addWidget(self.leader_input)

        layout.addLayout(form_layout)

        # Botões de ação
        btn_layout = QHBoxLayout()

        self.configure_btn = QPushButton("Configurar")
        self.configure_btn.clicked.connect(self.on_configure)
        btn_layout.addWidget(self.configure_btn)

        self.start_stop_btn = QPushButton("Iniciar Análise")
        self.start_stop_btn.clicked.connect(self.on_start_stop)
        btn_layout.addWidget(self.start_stop_btn)

        layout.addLayout(btn_layout)

        # Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Parado")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        status_layout.addWidget(self.status_label)
        layout.addLayout(status_layout)

        # Status TAKT
        takt_layout = QHBoxLayout()
        takt_label_title = QLabel("Etapa Takt:")
        self.status_takt = QLabel("...")
        self.status_takt.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        takt_layout.addWidget(takt_label_title)
        takt_layout.addWidget(self.status_takt)
        layout.addLayout(takt_layout)

        self.setLayout(layout)

        # Inicia com os inputs desabilitados
        self.set_inputs_enabled(False)

    def set_inputs_enabled(self, enabled: bool):
        self.cell_input.setReadOnly(not enabled)
        self.factory_input.setReadOnly(not enabled)
        self.leader_input.setReadOnly(not enabled)

    def _load(self):
        cfg = load_config()
        self.cell_input.setText(cfg.get("cell_number", ""))
        self.factory_input.setText(cfg.get("factory", ""))
        self.leader_input.setText(cfg.get("cell_leader", ""))

    def on_configure(self):
        # Alterna o modo de edição. Se estiver saindo do modo de edição -> salvar
        currently_readonly = self.cell_input.isReadOnly()
        if currently_readonly:
            # Habilita edição
            self.start_stop_btn.setDisabled(True)  # desabilita enquanto edita
            self.set_inputs_enabled(True)
            self.configure_btn.setText("Salvar Configuração")
        else:
            # Salva e desabilita edição
            self.start_stop_btn.setDisabled(False)  # reabilita

            data = {
                "cell_number": self.cell_input.text().strip(),
                "factory": self.factory_input.text().strip(),
                "cell_leader": self.leader_input.text().strip(),
            }
            try:
                save_config(data)
                QMessageBox.information(
                    self, "Configuração", "Configuração salva com sucesso."
                )
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao salvar configuração: {e}")
            self.set_inputs_enabled(False)
            self.configure_btn.setText("Configurar")

    def on_start_stop(self):
        print("Iniciando/parando análise...")
        if not self._analysis_running:
            # Start analysis: check that config exists
            cfg = load_config()
            if not (
                cfg.get("cell_number") and cfg.get("factory") and cfg.get("cell_leader")
            ):
                reply = QMessageBox.question(
                    self,
                    "Configuração incompleta",
                    "A configuração está incompleta. Deseja editar agora?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.set_inputs_enabled(True)
                    self.configure_btn.setText("Salvar Configuração")
                    return

            # iniciar análise
            self._analysis_running = True
            self.start_stop_btn.setText("Parar Análise")
            self.status_label.setText("Executando")
            # Desabilitar edição de inputs enquanto roda
            self.set_inputs_enabled(False)
            self.configure_btn.setText("Configurar")

            # Iniciar worker em thread separada
            if self._worker_thread is None or not self._worker_thread.isRunning():
                self._worker_thread = AsyncWorker(self)
                # Conecta o sinal do worker para atualizar o label na UI
                self._worker_thread.status_update.connect(self.on_worker_status_update)
                self._worker_thread.start()
        else:
            # parar
            self._analysis_running = False
            self.start_stop_btn.setText("Iniciar Análise")
            self.status_label.setText("Parado")
            # Solicitar parada do worker e aguardar finalizar
            if self._worker_thread and self._worker_thread.isRunning():
                self._worker_thread.stop()
                self._worker_thread.wait(5000)  # aguarda até 5s

    def on_worker_status_update(self, data: dict):
        if data.get("event") == "takt_screen_detected":
            self.takt_screen_working = True
            self.status_label.setText("Analisando")
            self.last_takt_screen_check = time.monotonic()
            self.status_takt.setText(str(self.last_takt_time_count))

        elif data.get("event") == "takt_detected":
            self.takt_screen_working = True
            self.status_label.setText("Analisando")
            self.last_takt_screen_check = time.monotonic()
            # Atualiza o status da label takt (UI)
            self.last_takt_time_count = data.get("takt", self.last_takt_time_count)
            self.status_takt.setText(str(self.last_takt_time_count))

            # Reseta o contador após chegar na etapa 3 com um timer de 3 segundos
            if self.last_takt_time_count == 3:
                if not hasattr(self, "_takt_reset_timer"):
                    self._takt_reset_timer = QTimer(self)
                    self._takt_reset_timer.setSingleShot(True)
                    self._takt_reset_timer.timeout.connect(
                        lambda: self.status_takt.setText("0")
                    )
                # Reinicia o timer para 3 segundos
                self._takt_reset_timer.start(3000)

        # logging.info(f"Worker event: {data.get('event')} - {data}")

    def _check_takt_screen_status(self):
        # Desativa se passou do limite
        if self.takt_screen_working and self.last_takt_screen_check is not None:
            if (time.monotonic() - self.last_takt_screen_check) > self.takt_timeout_sec:
                # Continuar daqui
                # TODO: Enviar mensagem a rabbitmq para acionar alarme de takt offline
                print("Tempo máximo de Tela Takt offline alcançado!")
                self.takt_screen_working = False
                self._analysis_running = False
                self.status_label.setText("Takt Fechado!")
                self.status_takt.setText("...")

    def closeEvent(self, event):
        # Garantir que worker é finalizado ao fechar janela
        try:
            if self._worker_thread and self._worker_thread.isRunning():
                self._worker_thread.stop()
                self._worker_thread.wait(5000)
        finally:
            event.accept()


class AsyncWorker(QThread):
    """Runs the async tracker_main in a dedicated event loop/thread."""

    status_update = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop = None
        self._task = None
        self._stop = None
        self._pre_stop = False

    def run(self):
        try:
            # Each thread needs its own event loop
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            # Create the stop event bound to this loop
            self._stop = asyncio.Event()

            async def runner():
                # Lazy import to avoid Qt/CV2 plugin path conflicts at startup
                tracker_main = importlib.import_module("main").main

                # Callback chamado pelo main
                def on_event(event_name: str, payload: dict):
                    self.status_update.emit({"event": event_name, **payload})

                # Start tracker in parallel with a stop waiter
                tracker = self._loop.create_task(tracker_main(on_event=on_event))

                async def stop_waiter():
                    await self._stop.wait()
                    # Cancel the tracker when stop requested
                    tracker.cancel()

                # If stop was requested before loop started, trigger it now
                if self._pre_stop:
                    self._stop.set()

                stopper = self._loop.create_task(stop_waiter())
                try:
                    await asyncio.wait(
                        [tracker, stopper], return_when=asyncio.FIRST_COMPLETED
                    )

                finally:
                    # Ensure tracker is cancelled and awaited
                    if not tracker.done():
                        tracker.cancel()
                        try:
                            await tracker
                        except asyncio.CancelledError:
                            pass
                    # Cancel stopper too
                    if not stopper.done():
                        stopper.cancel()
                        try:
                            await stopper
                        except asyncio.CancelledError:
                            pass

            self._loop.run_until_complete(runner())
        finally:
            if self._loop is not None:
                self._loop.stop()
                self._loop.close()
                self._loop = None

    def stop(self):
        # Signal the async task to stop
        try:
            if self._loop and not self._loop.is_closed() and self._stop is not None:
                self._loop.call_soon_threadsafe(self._stop.set)
            else:
                # Loop not started yet; remember to stop on start
                self._pre_stop = True
        except Exception:
            pass


def main():
    # Ensure Qt uses PyQt5's platform plugins, not OpenCV's
    try:
        pyqt_plugins = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        if pyqt_plugins:
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = pyqt_plugins
        # Remove conflicting plugin path if set by other libs
        os.environ.pop("QT_PLUGIN_PATH", None)
    except Exception:
        pass

    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
