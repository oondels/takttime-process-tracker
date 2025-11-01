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
    QDialog,
    QGroupBox,
    QFormLayout,
    QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QThread, QLibraryInfo, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
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


class ConfigDialog(QDialog):
    """Janela de diálogo dedicada para configurações"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do Sistema")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._build_ui()
        self._load_current_config()

    def _build_ui(self):
        main_layout = QVBoxLayout()

        # Título e descrição
        title = QLabel("Configurações do Rastreador de Takt-Time")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        description = QLabel(
            "Configure os parâmetros da célula de produção para iniciar o monitoramento."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666; padding: 10px;")
        description.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(description)

        # Group Box para informações da célula
        cell_group = QGroupBox("Informações da Célula")
        cell_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setContentsMargins(20, 20, 20, 20)

        # Campo Número da Célula
        self.cell_input = QLineEdit()
        self.cell_input.setPlaceholderText("Ex: Célula 01")
        self.cell_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        )
        cell_label = QLabel("Número da Célula:")
        cell_label.setStyleSheet("font-weight: normal;")
        form_layout.addRow(cell_label, self.cell_input)

        # Campo Fábrica
        self.factory_input = QLineEdit()
        self.factory_input.setPlaceholderText("Ex: Fábrica Principal")
        self.factory_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        )
        factory_label = QLabel("Fábrica:")
        factory_label.setStyleSheet("font-weight: normal;")
        form_layout.addRow(factory_label, self.factory_input)

        # Campo Líder da Célula
        self.leader_input = QLineEdit()
        self.leader_input.setPlaceholderText("Ex: João Silva")
        self.leader_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        )
        leader_label = QLabel("Líder da Célula:")
        leader_label.setStyleSheet("font-weight: normal;")
        form_layout.addRow(leader_label, self.leader_input)

        cell_group.setLayout(form_layout)
        main_layout.addWidget(cell_group)

        # Botões de ação
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Save).setText("Salvar")
        button_box.button(QDialogButtonBox.Cancel).setText("Cancelar")

        # Estilizar botões
        button_box.button(QDialogButtonBox.Save).setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        button_box.button(QDialogButtonBox.Cancel).setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """
        )

        button_box.accepted.connect(self.on_save)
        button_box.rejected.connect(self.reject)

        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _load_current_config(self):
        """Carrega a configuração atual nos campos"""
        cfg = load_config()
        self.cell_input.setText(cfg.get("cell_number", ""))
        self.factory_input.setText(cfg.get("factory", ""))
        self.leader_input.setText(cfg.get("cell_leader", ""))

    def on_save(self):
        """Valida e salva a configuração"""
        cell = self.cell_input.text().strip()
        factory = self.factory_input.text().strip()
        leader = self.leader_input.text().strip()

        # Validação básica
        if not cell or not factory or not leader:
            QMessageBox.warning(
                self,
                "Campos Obrigatórios",
                "Por favor, preencha todos os campos antes de salvar.",
            )
            return

        # Salvar configuração
        data = {"cell_number": cell, "factory": factory, "cell_leader": leader}

        try:
            save_config(data)
            QMessageBox.information(
                self,
                "Sucesso",
                "Configuração salva com sucesso!\n\nVocê já pode iniciar a análise.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar configuração:\n{e}")

    def get_config(self):
        """Retorna a configuração atual dos campos"""
        return {
            "cell_number": self.cell_input.text().strip(),
            "factory": self.factory_input.text().strip(),
            "cell_leader": self.leader_input.text().strip(),
        }


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

        # Cabeçalho estilizado
        header_layout = QVBoxLayout()
        title = QLabel("Takt-Time Process Tracker")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #2c3e50; padding: 15px;")
        header_layout.addWidget(title)

        subtitle = QLabel("Monitoramento Inteligente de Linha de Produção")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #7f8c8d; padding-bottom: 15px; font-size: 11pt;")
        header_layout.addWidget(subtitle)

        layout.addLayout(header_layout)

        # Seção de Informações da Configuração
        config_group = QGroupBox("Configuração Atual")
        config_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #ecf0f1;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #2980b9;
            }
        """
        )

        config_layout = QFormLayout()
        config_layout.setSpacing(10)
        config_layout.setContentsMargins(20, 20, 20, 20)

        # Labels somente leitura para exibir configuração
        self.cell_display = QLabel("--")
        self.cell_display.setStyleSheet(
            "padding: 8px; background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;"
        )
        config_layout.addRow("Célula:", self.cell_display)

        self.factory_display = QLabel("--")
        self.factory_display.setStyleSheet(
            "padding: 8px; background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;"
        )
        config_layout.addRow("Fábrica:", self.factory_display)

        self.leader_display = QLabel("--")
        self.leader_display.setStyleSheet(
            "padding: 8px; background-color: white; border: 1px solid #bdc3c7; border-radius: 3px;"
        )
        config_layout.addRow("Líder:", self.leader_display)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.configure_btn = QPushButton("⚙️ Configurar")
        self.configure_btn.setMinimumHeight(45)
        self.configure_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """
        )
        self.configure_btn.clicked.connect(self.on_configure)
        btn_layout.addWidget(self.configure_btn)

        self.start_stop_btn = QPushButton("▶️ Iniciar Análise")
        self.start_stop_btn.setMinimumHeight(45)
        self.start_stop_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """
        )
        self.start_stop_btn.clicked.connect(self.on_start_stop)
        btn_layout.addWidget(self.start_stop_btn)

        layout.addLayout(btn_layout)

        # Status em cards separados
        status_container = QHBoxLayout()
        status_container.setSpacing(10)

        # Card Status Geral
        status_card = QGroupBox("Status do Sistema")
        status_card.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #95a5a6;
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #34495e;
            }
        """
        )
        status_layout = QVBoxLayout()
        self.status_label = QLabel("⏸️ Parado")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: #e74c3c; padding: 15px;"
        )
        status_layout.addWidget(self.status_label)
        status_card.setLayout(status_layout)
        status_container.addWidget(status_card)

        # Card Etapa Takt
        takt_card = QGroupBox("Etapa Takt Atual")
        takt_card.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #95a5a6;
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #34495e;
            }
        """
        )
        takt_layout = QVBoxLayout()
        self.status_takt = QLabel("--")
        self.status_takt.setAlignment(Qt.AlignCenter)
        self.status_takt.setStyleSheet(
            "font-size: 24pt; font-weight: bold; color: #16a085; padding: 15px;"
        )
        takt_layout.addWidget(self.status_takt)
        takt_card.setLayout(takt_layout)
        status_container.addWidget(takt_card)

        layout.addLayout(status_container)

        self.setLayout(layout)
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

    def _load(self):
        """Carrega e exibe a configuração atual"""
        cfg = load_config()
        self.cell_display.setText(cfg.get("cell_number", "--"))
        self.factory_display.setText(cfg.get("factory", "--"))
        self.leader_display.setText(cfg.get("cell_leader", "--"))

    def on_configure(self):
        """Abre o diálogo de configuração"""
        dialog = ConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Atualiza a exibição após salvar
            self._load()

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
                    self.on_configure()
                return

            # iniciar análise
            self._analysis_running = True
            self.start_stop_btn.setText("⏹️ Parar Análise")
            self.start_stop_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 11pt;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """
            )
            self.status_label.setText("▶️ Executando")
            self.status_label.setStyleSheet(
                "font-size: 14pt; font-weight: bold; color: #27ae60; padding: 15px;"
            )
            self.configure_btn.setEnabled(False)

            # Iniciar worker em thread separada
            if self._worker_thread is None or not self._worker_thread.isRunning():
                self._worker_thread = AsyncWorker(self)
                # Conecta o sinal do worker para atualizar o label na UI
                self._worker_thread.status_update.connect(self.on_worker_status_update)
                self._worker_thread.start()
        else:
            # parar
            self._analysis_running = False
            self.start_stop_btn.setText("▶️ Iniciar Análise")
            self.start_stop_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 11pt;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
                QPushButton:pressed {
                    background-color: #1e8449;
                }
                QPushButton:disabled {
                    background-color: #95a5a6;
                }
            """
            )
            self.status_label.setText("⏸️ Parado")
            self.status_label.setStyleSheet(
                "font-size: 14pt; font-weight: bold; color: #e74c3c; padding: 15px;"
            )
            self.configure_btn.setEnabled(True)
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
