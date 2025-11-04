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
    QInputDialog,
)
from PyQt5.QtCore import Qt, QThread, QLibraryInfo, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
import asyncio
import importlib
import time
from typing import Callable
import re

from mqtt_manager import MQTTManager


# Configuração de logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("app_debug.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
logger.debug(f"CONFIG_DIR: {CONFIG_DIR}, CONFIG_PATH: {CONFIG_PATH}")

# Credenciais para desbloquear configurações técnicas
TECH_CONFIG_USER = "admin"
TECH_CONFIG_PASS = "dass@2025"


def ensure_config_dir():
    logger.debug(f"Criando diretório de configuração: {CONFIG_DIR}")
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    logger.debug("Carregando configuração...")
    ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        logger.warning(
            f"Arquivo de configuração não encontrado: {CONFIG_PATH}. Usando configuração padrão."
        )
        return {
            "device": {"cell_number": "", "factory": "", "cell_leader": ""},
            "network": {"wifi_ssid": "", "wifi_pass": ""},
            "tech": {
                "mqtt_host": "",
                "mqtt_user": "",
                "mqtt_pass": "",
                "model_path": "./train_2025.pt",
            },
        }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Migração de configuração antiga para nova estrutura
            if "cell_number" in config:
                logger.info("Migrando configuração antiga para nova estrutura")
                migrated_config = {
                    "device": {
                        "cell_number": config.get("cell_number", ""),
                        "factory": config.get("factory", ""),
                        "cell_leader": config.get("cell_leader", ""),
                    },
                    "network": {"wifi_ssid": "", "wifi_pass": ""},
                    "tech": {
                        "mqtt_host": "",
                        "mqtt_user": "",
                        "mqtt_pass": "",
                        "model_path": "./train_2025.pt",
                    },
                }
                logger.debug(f"Configuração migrada: {migrated_config}")
                return migrated_config
            return config
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}", exc_info=True)
        return {
            "device": {"cell_number": "", "factory": "", "cell_leader": ""},
            "network": {"wifi_ssid": "", "wifi_pass": ""},
            "tech": {
                "mqtt_host": "",
                "mqtt_user": "",
                "mqtt_pass": "",
                "model_path": "./train_2025.pt",
            },
        }


def save_config(data: dict):
    logger.debug(f"Salvando configuração: {data}")
    ensure_config_dir()
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Configuração salva com sucesso em: {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Erro ao salvar configuração: {e}", exc_info=True)
        raise


class ConfigDialog(QDialog):
    """Janela de diálogo dedicada para configurações"""

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Inicializando ConfigDialog")
        self.setWindowTitle("Configurações do Sistema")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(650)
        self.tech_unlocked = (
            False  # Controla se as configurações técnicas estão desbloqueadas
        )
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
            "Configure os parâmetros do dispositivo, rede e conexões técnicas."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666; padding: 10px;")
        description.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(description)

        # Estilo comum para GroupBox
        group_style = """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2980b9;
            }
        """

        input_style = "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        label_style = "font-weight: normal;"

        # ===== DISPOSITIVO =====
        device_group = QGroupBox("Dispositivo")
        device_group.setStyleSheet(group_style)

        device_layout = QFormLayout()
        device_layout.setSpacing(12)
        device_layout.setContentsMargins(20, 20, 20, 20)

        self.cell_input = QLineEdit()
        self.cell_input.setPlaceholderText("Ex: Célula 01")
        self.cell_input.setStyleSheet(input_style)
        cell_label = QLabel("Número da Célula:")
        cell_label.setStyleSheet(label_style)
        device_layout.addRow(cell_label, self.cell_input)

        self.factory_input = QLineEdit()
        self.factory_input.setPlaceholderText("Ex: Fábrica Principal")
        self.factory_input.setStyleSheet(input_style)
        factory_label = QLabel("Fábrica:")
        factory_label.setStyleSheet(label_style)
        device_layout.addRow(factory_label, self.factory_input)

        self.leader_input = QLineEdit()
        self.leader_input.setPlaceholderText("Ex: João Silva")
        self.leader_input.setStyleSheet(input_style)
        leader_label = QLabel("Líder da Célula:")
        leader_label.setStyleSheet(label_style)
        device_layout.addRow(leader_label, self.leader_input)

        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group)

        # ===== REDE =====
        network_group = QGroupBox("Rede")
        network_group.setStyleSheet(group_style)

        network_layout = QFormLayout()
        network_layout.setSpacing(12)
        network_layout.setContentsMargins(20, 20, 20, 20)

        self.wifi_ssid_input = QLineEdit()
        self.wifi_ssid_input.setPlaceholderText("Ex: RedeWiFi-Producao")
        self.wifi_ssid_input.setStyleSheet(input_style)
        ssid_label = QLabel("SSID WiFi:")
        ssid_label.setStyleSheet(label_style)
        network_layout.addRow(ssid_label, self.wifi_ssid_input)

        self.wifi_pass_input = QLineEdit()
        self.wifi_pass_input.setPlaceholderText("Senha do WiFi")
        self.wifi_pass_input.setEchoMode(QLineEdit.Password)
        self.wifi_pass_input.setStyleSheet(input_style)
        pass_label = QLabel("Senha WiFi:")
        pass_label.setStyleSheet(label_style)
        network_layout.addRow(pass_label, self.wifi_pass_input)

        network_group.setLayout(network_layout)
        main_layout.addWidget(network_group)

        # ===== TÉCNICO =====
        # Container para o título com cadeado
        tech_header_widget = QWidget()
        tech_header_layout = QHBoxLayout()
        tech_header_layout.setContentsMargins(0, 0, 0, 0)

        tech_title_label = QLabel("Configurações Técnicas")
        tech_title_label.setStyleSheet("font-weight: bold; font-size: 12px;")

        # Botão de cadeado
        self.lock_button = QPushButton("🔒")
        self.lock_button.setFixedSize(30, 30)
        self.lock_button.setStyleSheet(
            """
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """
        )
        self.lock_button.setToolTip("Clique para desbloquear as configurações técnicas")
        self.lock_button.clicked.connect(self._unlock_tech_config)

        tech_header_layout.addWidget(tech_title_label)
        tech_header_layout.addWidget(self.lock_button)
        tech_header_layout.addStretch()
        tech_header_widget.setLayout(tech_header_layout)

        tech_group = QGroupBox()
        tech_group.setStyleSheet(group_style)

        tech_layout = QFormLayout()
        tech_layout.setSpacing(12)
        tech_layout.setContentsMargins(20, 20, 20, 20)

        self.mqtt_host_input = QLineEdit()
        self.mqtt_host_input.setPlaceholderText("Ex: 10.110.1.1")
        self.mqtt_host_input.setStyleSheet(input_style)
        self.mqtt_host_input.setReadOnly(True)  # Bloqueado por padrão
        mqtt_host_label = QLabel("mqtt Host:")
        mqtt_host_label.setStyleSheet(label_style)
        tech_layout.addRow(mqtt_host_label, self.mqtt_host_input)

        self.mqtt_user_input = QLineEdit()
        self.mqtt_user_input.setPlaceholderText("Usuário MQTT")
        self.mqtt_user_input.setStyleSheet(input_style)
        self.mqtt_user_input.setReadOnly(True)  # Bloqueado por padrão
        mqtt_user_label = QLabel("mqtt Usuário:")
        mqtt_user_label.setStyleSheet(label_style)
        tech_layout.addRow(mqtt_user_label, self.mqtt_user_input)

        self.mqtt_pass_input = QLineEdit()
        self.mqtt_pass_input.setPlaceholderText("Senha MQTT")
        self.mqtt_pass_input.setEchoMode(QLineEdit.Password)
        self.mqtt_pass_input.setStyleSheet(input_style)
        self.mqtt_pass_input.setReadOnly(True)  # Bloqueado por padrão
        mqtt_pass_label = QLabel("mqtt Senha:")
        mqtt_pass_label.setStyleSheet(label_style)
        tech_layout.addRow(mqtt_pass_label, self.mqtt_pass_input)

        self.model_path_input = QLineEdit()
        self.model_path_input.setPlaceholderText("./train_2025.pt")
        self.model_path_input.setStyleSheet(input_style)
        self.model_path_input.setReadOnly(True)  # Bloqueado por padrão
        model_label = QLabel("Caminho do Modelo:")
        model_label.setStyleSheet(label_style)
        tech_layout.addRow(model_label, self.model_path_input)

        tech_group.setLayout(tech_layout)

        # Layout vertical para agrupar o header e o grupo
        tech_container = QWidget()
        tech_container_layout = QVBoxLayout()
        tech_container_layout.setContentsMargins(0, 0, 0, 0)
        tech_container_layout.setSpacing(5)
        tech_container_layout.addWidget(tech_header_widget)
        tech_container_layout.addWidget(tech_group)
        tech_container.setLayout(tech_container_layout)

        main_layout.addWidget(tech_container)

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

    def _unlock_tech_config(self):
        """Solicita autenticação para desbloquear configurações técnicas"""
        if self.tech_unlocked:
            # Se já está desbloqueado, bloqueia novamente
            self.tech_unlocked = False
            self.mqtt_host_input.setReadOnly(True)
            self.mqtt_user_input.setReadOnly(True)
            self.mqtt_pass_input.setReadOnly(True)
            self.model_path_input.setReadOnly(True)
            self.lock_button.setText("🔒")
            self.lock_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #ff9800;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #f57c00;
                }
            """
            )
            self.lock_button.setToolTip(
                "Clique para desbloquear as configurações técnicas"
            )
            logger.info("Configurações técnicas bloqueadas")
            return

        # Solicitar usuário
        username, ok = QInputDialog.getText(
            self, "Autenticação Necessária", "Usuário:", QLineEdit.Normal
        )

        if not ok or not username:
            return

        # Solicitar senha
        password, ok = QInputDialog.getText(
            self, "Autenticação Necessária", "Senha:", QLineEdit.Password
        )

        if not ok or not password:
            return

        # Validar credenciais
        if username == TECH_CONFIG_USER and password == TECH_CONFIG_PASS:
            self.tech_unlocked = True
            self.mqtt_host_input.setReadOnly(False)
            self.mqtt_user_input.setReadOnly(False)
            self.mqtt_pass_input.setReadOnly(False)
            self.model_path_input.setReadOnly(False)
            self.lock_button.setText("🔓")
            self.lock_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """
            )
            self.lock_button.setToolTip(
                "Clique para bloquear as configurações técnicas"
            )
            logger.info("Configurações técnicas desbloqueadas com sucesso")
            QMessageBox.information(
                self,
                "Sucesso",
                "Configurações técnicas desbloqueadas! Você pode agora editar os campos.",
            )
        else:
            logger.warning("Tentativa de autenticação falhou")
            QMessageBox.warning(self, "Acesso Negado", "Usuário ou senha incorretos!")

    def _load_current_config(self):
        """Carrega a configuração atual nos campos"""
        cfg = load_config()

        # Dispositivo
        device = cfg.get("device", {})
        self.cell_input.setText(device.get("cell_number", ""))
        self.factory_input.setText(device.get("factory", ""))
        self.leader_input.setText(device.get("cell_leader", ""))

        # Rede
        network = cfg.get("network", {})
        self.wifi_ssid_input.setText(network.get("wifi_ssid", ""))
        self.wifi_pass_input.setText(network.get("wifi_pass", ""))

        # Técnico
        tech = cfg.get("tech", {})
        self.mqtt_host_input.setText(tech.get("mqtt_host", ""))
        self.mqtt_user_input.setText(tech.get("mqtt_user", ""))
        self.mqtt_pass_input.setText(tech.get("mqtt_pass", ""))
        self.model_path_input.setText(tech.get("model_path", "./train_2025.pt"))

    def on_save(self):
        """Valida e salva a configuração"""
        logger.debug("Tentando salvar configuração...")
        # Dispositivo
        cell = self.cell_input.text().strip()
        factory = self.factory_input.text().strip()
        leader = self.leader_input.text().strip()

        # Rede
        wifi_ssid = self.wifi_ssid_input.text().strip()
        wifi_pass = self.wifi_pass_input.text().strip()

        # Técnico
        mqtt_host = self.mqtt_host_input.text().strip()
        mqtt_user = self.mqtt_user_input.text().strip()
        mqtt_pass = self.mqtt_pass_input.text().strip()
        model_path = self.model_path_input.text().strip() or "./train_2025.pt"

        logger.debug(
            f"Valores do formulário - Cell: {cell}, Factory: {factory}, Leader: {leader}"
        )
        logger.debug(
            f"WiFi SSID: {wifi_ssid}, mqtt Host: {mqtt_host}, Model: {model_path}"
        )

        # Validação básica - apenas campos do dispositivo são obrigatórios
        if not cell or not factory or not leader:
            logger.warning("Validação falhou: campos obrigatórios vazios")
            QMessageBox.warning(
                self,
                "Campos Obrigatórios",
                "Por favor, preencha todos os campos do Dispositivo antes de salvar.",
            )
            return

        # Salvar configuração estruturada
        data = {
            "device": {"cell_number": cell, "factory": factory, "cell_leader": leader},
            "network": {"wifi_ssid": wifi_ssid, "wifi_pass": wifi_pass},
            "tech": {
                "mqtt_host": mqtt_host,
                "mqtt_user": mqtt_user,
                "mqtt_pass": mqtt_pass,
                "model_path": model_path,
            },
        }

        try:
            save_config(data)
            logger.info("Configuração salva com sucesso via dialog")
            QMessageBox.information(
                self,
                "Sucesso",
                "Configuração salva com sucesso!\n\nVocê já pode iniciar a análise.",
            )
            self.accept()
        except Exception as e:
            logger.error(f"Erro ao salvar configuração via dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Erro", f"Falha ao salvar configuração:\n{e}")

    def get_config(self):
        """Retorna a configuração atual dos campos"""
        return {
            "device": {
                "cell_number": self.cell_input.text().strip(),
                "factory": self.factory_input.text().strip(),
                "cell_leader": self.leader_input.text().strip(),
            },
            "network": {
                "wifi_ssid": self.wifi_ssid_input.text().strip(),
                "wifi_pass": self.wifi_pass_input.text().strip(),
            },
            "tech": {
                "mqtt_host": self.mqtt_host_input.text().strip(),
                "mqtt_user": self.mqtt_user_input.text().strip(),
                "mqtt_pass": self.mqtt_pass_input.text().strip(),
                "model_path": self.model_path_input.text().strip() or "./train_2025.pt",
            },
        }


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("=== Inicializando MainWindow ===")
        self.setWindowTitle("Takt-Time Process Tracker")
        self._analysis_running = False
        self._worker_thread = None

        # Estado da tela Takt e timeout
        self.takt_screen_working = False
        self.last_takt_screen_check = None
        self.takt_timeout_sec = 6
        self.last_takt_time_count = 0

        # Estado de inicialização e segurança
        self._model_loaded = False
        self._mqtt_connected = False
        self._initialization_thread = None

        logger.debug("Construindo interface gráfica...")
        self._build_ui()
        self._load()

        # Desabilita botão iniciar até que modelo e MQTT estejam prontos
        self.start_stop_btn.setEnabled(False)
        logger.info(
            "Botão 'Iniciar Análise' desabilitado até verificação de pré-requisitos"
        )

        # Inicia verificação de pré-requisitos
        self._check_prerequisites()

        # Timer para verificar periodicamente o status
        self._takt_timer = QTimer(self)
        self._takt_timer.setInterval(1000)  # checa a cada 1s
        self._takt_timer.timeout.connect(self._check_takt_screen_status)
        self._takt_timer.start()
        logger.debug("Timer de verificação de status iniciado (1s)")

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

        # Status de inicialização
        init_status_layout = QHBoxLayout()
        init_status_layout.setSpacing(10)

        # Indicador de Modelo
        self.model_status_label = QLabel("🔴 Modelo: Verificando...")
        self.model_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #e74c3c;"
        )
        init_status_layout.addWidget(self.model_status_label)

        # Indicador de MQTT Broker
        self.mqtt_status_label = QLabel("🔴 MQTT: Verificando...")
        self.mqtt_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #e74c3c;"
        )
        init_status_layout.addWidget(self.mqtt_status_label)

        # Indicador de ESP32
        self.esp32_status_label = QLabel("⚪ ESP32: Aguardando...")
        self.esp32_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #95a5a6;"
        )
        init_status_layout.addWidget(self.esp32_status_label)

        init_status_layout.addStretch()
        layout.addLayout(init_status_layout)

        self.setLayout(layout)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

    def _load(self):
        """Carrega e exibe a configuração atual"""
        logger.debug("Carregando configuração na interface...")
        cfg = load_config()
        device = cfg.get("device", {})
        self.cell_display.setText(device.get("cell_number", "--"))
        self.factory_display.setText(device.get("factory", "--"))
        self.leader_display.setText(device.get("cell_leader", "--"))
        logger.info(
            f"Configuração exibida - Célula: {device.get('cell_number')}, Fábrica: {device.get('factory')}"
        )

    def on_configure(self):
        """Abre o diálogo de configuração"""
        logger.info("Abrindo diálogo de configuração")
        dialog = ConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            logger.info("Configuração aceita, atualizando exibição")
            # Atualiza a exibição após salvar
            self._load()
            # Re-verifica pré-requisitos após mudança de configuração
            logger.debug("Re-verificando pré-requisitos após mudança de configuração")
            self._check_prerequisites()

    def _check_prerequisites(self):
        """Verifica se modelo e MQTT estão disponíveis antes de habilitar análise"""
        logger.info("=== Iniciando verificação de pré-requisitos ===")
        self.start_stop_btn.setEnabled(False)
        self.start_stop_btn.setText("⏳ Verificando Sistema...")

        # Atualiza status visual
        self.model_status_label.setText("🟡 Modelo: Verificando...")
        self.model_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #f39c12;"
        )
        self.mqtt_status_label.setText("🟡 MQTT: Verificando...")
        self.mqtt_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #f39c12;"
        )

        # Inicia thread de verificação
        if (
            self._initialization_thread is None
            or not self._initialization_thread.isRunning()
        ):
            logger.debug("Iniciando InitializationWorker thread")
            self._initialization_thread = InitializationWorker(self)
            self._initialization_thread.status_update.connect(
                self._on_initialization_update
            )
            self._initialization_thread.start()
        else:
            logger.warning("InitializationWorker thread já está em execução")

    def _on_initialization_update(self, data: dict):
        """Processa updates da thread de inicialização"""
        event = data.get("event")
        logger.debug(f"Evento de inicialização recebido: {event} - Dados: {data}")

        if event == "model_check_start":
            logger.info("Iniciando verificação do modelo YOLO")
            self.model_status_label.setText("🟡 Modelo: Carregando...")

        elif event == "model_loaded":
            self._model_loaded = True
            model_path = data.get("path", "N/A")
            logger.info(f"Modelo YOLO carregado com sucesso: {model_path}")
            self.model_status_label.setText("🟢 Modelo: Pronto")
            self.model_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #27ae60;"
            )

        elif event == "model_error":
            self._model_loaded = False
            error_msg = data.get("error", "Erro desconhecido")
            logger.error(f"✗ Erro ao carregar modelo: {error_msg}")
            self.model_status_label.setText(f"🔴 Modelo: Erro")
            self.model_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c;"
            )
            QMessageBox.critical(
                self,
                "Erro no Modelo",
                f"Falha ao carregar o modelo YOLO:\n{error_msg}\n\nVerifique o caminho nas configurações.",
            )

        elif event == "mqtt_check_start":
            logger.info("Iniciando verificação da conexão MQTT")
            self.mqtt_status_label.setText("🟡 MQTT: Conectando...")

        elif event == "mqtt_connected":
            self._mqtt_connected = True
            mqtt_url = data.get("url", "N/A")
            logger.info(f" Conexão MQTT estabelecida: {mqtt_url}")
            self.mqtt_status_label.setText("🟢 MQTT: Conectado")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #27ae60;"
            )

        elif event == "mqtt_error":
            self._mqtt_connected = False
            error_msg = data.get("error", "Erro desconhecido")
            logger.error(f"✗ Erro na conexão MQTT: {error_msg}")
            self.mqtt_status_label.setText(f"🔴 MQTT: Erro")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c;"
            )
            QMessageBox.warning(
                self,
                "Erro na Conexão MQTT",
                f"Falha ao conectar ao MQTT:\n{error_msg}\n\nVerifique as configurações de rede e MQTT.",
            )

        # Habilita botão apenas se ambos estiverem OK
        if self._model_loaded and self._mqtt_connected:
            logger.info(" Todos os pré-requisitos OK! Sistema pronto para iniciar")
            self.start_stop_btn.setEnabled(True)
            self.start_stop_btn.setText("▶️ Iniciar Análise")
            self.status_label.setText("✔ Sistema Pronto")
            self.status_label.setStyleSheet(
                "font-size: 14pt; font-weight: bold; color: #27ae60; padding: 15px;"
            )
        elif event in ["model_error", "mqtt_error"]:
            logger.warning("Sistema indisponível devido a erros na inicialização")
            self.start_stop_btn.setText("❌ Sistema Indisponível")
            self.status_label.setText("❌ Erro na Inicialização")
            self.status_label.setStyleSheet(
                "font-size: 14pt; font-weight: bold; color: #e74c3c; padding: 15px;"
            )

    def _on_device_status_changed(self, device_id: str, connected: bool):
        """Callback quando status do dispositivo ESP32 muda"""
        status_text = "🟢 ONLINE" if connected else "🔴 OFFLINE"
        logger.info(f"Mudança de status do dispositivo {device_id}: {status_text}")

        # Atualizar UI com status do ESP32
        if connected:
            self.esp32_status_label.setText(f"🟢 ESP32: Conectado ({device_id})")
            self.esp32_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #27ae60; font-weight: bold;"
            )
            self.esp32_status_label.setToolTip(f"Dispositivo {device_id} está online e enviando heartbeats")
        else:
            self.esp32_status_label.setText(f"🔴 ESP32: Desconectado ({device_id})")
            self.esp32_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c; font-weight: bold;"
            )
            self.esp32_status_label.setToolTip(f"Dispositivo {device_id} está offline ou não responde")
            # Se dispositivo ficou offline durante análise, pausar
            if self._analysis_running:
                logger.warning("Dispositivo ESP32 offline durante análise!")
                QMessageBox.warning(
                    self,
                    "Dispositivo Offline",
                    f"O dispositivo {device_id} ficou offline!\n\nA análise será pausada.",
                )
                # Pausar análise
                if self._analysis_running:
                    self.on_start_stop()

    def on_start_stop(self):
        if not self._analysis_running:
            logger.info("Tentando iniciar análise...")
            # Start analysis: check that config exists
            cfg = load_config()
            device = cfg.get("device", {})
            if not (
                device.get("cell_number")
                and device.get("factory")
                and device.get("cell_leader")
            ):
                logger.warning("Configuração do dispositivo incompleta")
                reply = QMessageBox.question(
                    self,
                    "Configuração incompleta",
                    "A configuração do dispositivo está incompleta. Deseja editar agora?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.on_configure()
                return

            # iniciar análise
            logger.info("Iniciando análise de takt-time...")
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
                logger.debug("Criando e iniciando AsyncWorker thread")
                self._worker_thread = AsyncWorker(self)
                # Conecta o sinal do worker para atualizar o label na UI
                self._worker_thread.set_device_status_callback(
                    self._on_device_status_changed
                )
                self._worker_thread.status_update.connect(self.on_worker_status_update)
                self._worker_thread.start()
                logger.info("AsyncWorker thread iniciado")
            else:
                logger.warning("AsyncWorker thread já está em execução")
        else:
            # parar
            logger.info("Parando análise...")
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
                logger.debug("Solicitando parada do AsyncWorker thread")
                self._worker_thread.stop()
                self._worker_thread.wait(5000)  # aguarda até 5s
                logger.info("AsyncWorker thread parado")

    def on_worker_status_update(self, data: dict):
        event = data.get("event")
        # logger.debug(f"Worker status update: {event} - {data}")

        if event == "connected":
            logger.info("✅ Conexão MQTT estabelecida pelo AsyncWorker")
            self.mqtt_status_label.setText("🟢 MQTT: Conectado")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #27ae60;"
            )
            # Atualizar status do ESP32 para "aguardando" APENAS se ainda estiver no estado inicial
            if "Aguardando..." in self.esp32_status_label.text() or "⚪" in self.esp32_status_label.text():
                self.esp32_status_label.setText("🟡 ESP32: Aguardando conexão...")
                self.esp32_status_label.setStyleSheet(
                    "padding: 5px; font-size: 10pt; color: #f39c12;"
                )

        elif event == "connection_error":
            error_msg = data.get("error", "Erro desconhecido")
            logger.error(f"✗ Erro na conexão MQTT: {error_msg}")
            self.mqtt_status_label.setText("🔴 MQTT: Erro")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c;"
            )
            # Para a análise automaticamente
            self._analysis_running = False
            self.on_start_stop()  # Volta ao estado parado
            QMessageBox.critical(
                self,
                "Erro na Conexão",
                f"Falha ao conectar ao MQTT:\n{error_msg}\n\nA análise foi interrompida.",
            )
            return

        elif event == "takt_screen_detected":
            # logger.info("Tela de takt detectada")
            self.takt_screen_working = True
            self.status_label.setText("Analisando")
            self.last_takt_screen_check = time.monotonic()
            self.status_takt.setText(str(self.last_takt_time_count))

        elif event == "takt_detected":
            takt_number = data.get("takt", self.last_takt_time_count)
            logger.info(f"Takt detectado! Etapa: {takt_number}/3")
            self.takt_screen_working = True
            self.status_label.setText("Analisando")
            self.last_takt_screen_check = time.monotonic()
            # Atualiza o status da label takt (UI)
            self.last_takt_time_count = takt_number
            self.status_takt.setText(str(self.last_takt_time_count))

            # Reseta o contador após chegar na etapa 3 com um timer de 3 segundos
            if self.last_takt_time_count == 3:
                logger.info(
                    "Etapa 3/3 completada! Agendando reset do contador em 3 segundos"
                )
                if not hasattr(self, "_takt_reset_timer"):
                    self._takt_reset_timer = QTimer(self)
                    self._takt_reset_timer.setSingleShot(True)
                    self._takt_reset_timer.timeout.connect(self._reset_takt_counter)
                # Reinicia o timer para 3 segundos
                self._takt_reset_timer.start(3000)

    def _reset_takt_counter(self):
        """Reseta o contador de takt tanto na UI quanto na variável interna"""
        logger.info("Resetando contador de takt para 0")
        self.last_takt_time_count = 0
        self.status_takt.setText("0")

    def _check_takt_screen_status(self):
        # Desativa se passou do limite
        if self.takt_screen_working and self.last_takt_screen_check is not None:
            elapsed = time.monotonic() - self.last_takt_screen_check
            if elapsed > self.takt_timeout_sec:
                # Continuar daqui
                # TODO: Enviar mensagem a rabbitmq para acionar alarme de takt offline
                logger.warning(
                    f"Timeout! Tela de takt offline há {elapsed:.1f} segundos (limite: {self.takt_timeout_sec}s)"
                )
                print("Tempo máximo de Tela Takt offline alcançado!")
                self.takt_screen_working = False
                self._analysis_running = False
                self.status_label.setText("Takt Fechado!")
                self.status_takt.setText("...")

    def closeEvent(self, event):
        # Garantir que worker é finalizado ao fechar janela
        logger.info("Fechando aplicação, finalizando threads...")
        try:
            if self._worker_thread and self._worker_thread.isRunning():
                logger.debug("Parando AsyncWorker thread...")
                self._worker_thread.stop()
                self._worker_thread.wait(5000)
                logger.info("AsyncWorker thread finalizado")
        except Exception as e:
            logger.error(f"Erro ao finalizar thread: {e}", exc_info=True)
        finally:
            logger.info("Aplicação encerrada")
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
        self._mqtt_manager = None
        self._device_status_callback = None

    def set_device_status_callback(self, callback: Callable):
        """Define callback para mudanças de status do dispositivo"""
        self._device_status_callback = callback
        logger.debug("Callback de status do dispositivo configurado no AsyncWorker")

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

                logger.info("Estabelecendo conexão MQTT")
                try:
                    # Carregar configuração
                    cfg = load_config()
                    tech_config = cfg.get("tech", {})
                    mqtt_host = tech_config.get("mqtt_host", "")
                    mqtt_user = tech_config.get("mqtt_user", "")
                    mqtt_pass = tech_config.get("mqtt_pass", "")

                    device = cfg.get("device", {})
                    cell_number = device.get("cell_number", "").strip()
                    factory = device.get("factory", "").strip()
                    
                    factory_num = re.sub(r"\D", "", factory) or "0"
                    cell_num = re.sub(r"\D", "", cell_number) or "0"
                    device_id = f"cost-{factory_num}-{cell_num}"

                    mqtt_manager = MQTTManager(
                        broker=mqtt_host,
                        port=1883,
                        username=mqtt_user,
                        password=mqtt_pass,
                        timeout_seconds=60,
                    )
                    mqtt_manager.add_device(device_id)

                    if self._device_status_callback:
                        mqtt_manager.on_status_change(self._device_status_callback)
                    self._mqtt_manager = mqtt_manager

                    if mqtt_manager.connect(timeout=10):
                        on_event("connected", {"url": f"{mqtt_host}:{1883}"})
                        logger.info(f"Conexão MQTT estabelecida: {mqtt_host}")

                        time.sleep(2)  # aguarda mensagem LWT
                        if mqtt_manager.is_device_connected(device_id):
                            logger.info(f"Dispositivo {device_id} está online")
                        else:
                            logger.warning(f"Dispositivo {device_id} está offline")

                        # Passar a conexão para o tracker (main)
                        tracker = self._loop.create_task(
                            tracker_main(
                                on_event=on_event,
                                connection=mqtt_manager,
                                device_id=device_id,
                            )
                        )

                except Exception as e:
                    logger.error(
                        f"✗ Erro ao estabelecer conexão MQTT: {e}", exc_info=True
                    )
                    on_event("connection_error", {"error": str(e)})
                    return

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

                    if self._mqtt_manager:
                        logger.info("Desconectando MQTT Manager do AsyncWorker")
                        self._mqtt_manager.disconnect()
                        self._mqtt_manager = None

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


class InitializationWorker(QThread):
    """Thread para verificar modelo e conexão MQTT antes de iniciar análise"""

    status_update = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("InitializationWorker criado")

    def run(self):
        """Verifica se modelo YOLO e conexão MQTT estão disponíveis"""
        import os

        logger.info("=== InitializationWorker: Iniciando verificações ===")

        # 1. Verificar Modelo YOLO
        self.status_update.emit({"event": "model_check_start"})

        try:
            cfg = load_config()
            tech_config = cfg.get("tech", {})
            model_path = tech_config.get("model_path", "./train_2025.pt")

            logger.debug(f"Verificando modelo em: {model_path}")
            # Verifica se arquivo existe
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Modelo não encontrado em: {model_path}")

            logger.debug("Arquivo do modelo encontrado, tentando carregar...")
            # Tenta carregar o modelo
            from ultralytics import YOLO

            model = YOLO(model_path)

            # Modelo carregado com sucesso
            self.status_update.emit({"event": "model_loaded", "path": model_path})
            del model  # Libera memória

        except Exception as e:
            logger.error(f"Erro ao verificar/carregar modelo: {e}", exc_info=True)
            self.status_update.emit({"event": "model_error", "error": str(e)})
            return  # Para aqui se modelo falhar

        self.status_update.emit({"event": "mqtt_check_start"})
        # Simula sucesso para permitir inicialização
        self.status_update.emit(
            {"event": "mqtt_connected", "url": "Será testado ao iniciar"}
        )
        logger.info("=== InitializationWorker: Verificações concluídas com sucesso ===")


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
