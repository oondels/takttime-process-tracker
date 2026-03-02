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


# Garantir que a pasta de logs existe
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Configuração de logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "app_debug.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
logger.debug(f"CONFIG_DIR: {CONFIG_DIR}, CONFIG_PATH: {CONFIG_PATH}")

# Credenciais para desbloquear configurações técnicas
TECH_CONFIG_USER = "admin"
TECH_CONFIG_PASS = "change-me-before-use"


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
        # cell_label = QLabel("Número da Célula:")
        # cell_label.setStyleSheet(label_style)
        # device_layout.addRow(cell_label, self.cell_input)

        self.factory_input = QLineEdit()
        self.factory_input.setPlaceholderText("Ex: Fábrica Principal")
        self.factory_input.setStyleSheet(input_style)
        # factory_label = QLabel("Fábrica:")
        # factory_label.setStyleSheet(label_style)
        # device_layout.addRow(factory_label, self.factory_input)

        self.leader_input = QLineEdit()
        self.leader_input.setPlaceholderText("Ex: Nome do lider")
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
        # ssid_label = QLabel("SSID WiFi:")
        # ssid_label.setStyleSheet(label_style)
        # network_layout.addRow(ssid_label, self.wifi_ssid_input)

        self.wifi_pass_input = QLineEdit()
        self.wifi_pass_input.setPlaceholderText("Senha do WiFi")
        self.wifi_pass_input.setEchoMode(QLineEdit.Password)
        self.wifi_pass_input.setStyleSheet(input_style)
        # pass_label = QLabel("Senha WiFi:")
        # pass_label.setStyleSheet(label_style)
        # network_layout.addRow(pass_label, self.wifi_pass_input)

        # network_group.setLayout(network_layout)
        # main_layout.addWidget(network_group)

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
        # self.cell_input.setText(device.get("cell_number", ""))
        # self.factory_input.setText(device.get("factory", ""))
        self.leader_input.setText(device.get("cell_leader", ""))

        # Rede
        # network = cfg.get("network", {})
        # self.wifi_ssid_input.setText(network.get("wifi_ssid", ""))
        # self.wifi_pass_input.setText(network.get("wifi_pass", ""))

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
        # cell = self.cell_input.text().strip()
        # factory = self.factory_input.text().strip()
        leader = self.leader_input.text().strip()

        # Rede
        # wifi_ssid = self.wifi_ssid_input.text().strip()
        # wifi_pass = self.wifi_pass_input.text().strip()

        # Técnico
        mqtt_host = self.mqtt_host_input.text().strip()
        mqtt_user = self.mqtt_user_input.text().strip()
        mqtt_pass = self.mqtt_pass_input.text().strip()
        model_path = self.model_path_input.text().strip() or "./train_2025.pt"

        # logger.debug(
        #     f"Valores do formulário - Cell: {cell}, Factory: {factory}, Leader: {leader}"
        # )
        # logger.debug(
        #     f"WiFi SSID: {wifi_ssid}, mqtt Host: {mqtt_host}, Model: {model_path}"
        # )

        # Validação básica - apenas campos do dispositivo são obrigatórios
        # if not cell or not factory or not leader:
        #     logger.warning("Validação falhou: campos obrigatórios vazios")
        #     QMessageBox.warning(
        #         self,
        #         "Campos Obrigatórios",
        #         "Por favor, preencha todos os campos do Dispositivo antes de salvar.",
        #     )
        #     return

        # Salvar configuração estruturada
        config = load_config()
        device_data = config.get("device", {})
        wifi_data = config.get("network", {})
        data = {
            "device": {"cell_number": device_data.get("cell_number", ""), "factory": device_data.get("factory", ""), "cell_leader": leader},
            "network": {"wifi_ssid": wifi_data.get("wifi_ssid",""), "wifi_pass": wifi_data.get("wifi_pass", "")},
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


class EditTaktDialog(QDialog):
    """Janela de diálogo para editar a contagem do takt"""

    def __init__(self, parent=None, current_takt=0):
        super().__init__(parent)
        logger.debug(f"Inicializando EditTaktDialog com takt atual: {current_takt}")
        self.setWindowTitle("Editar Takt Time")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)
        self.current_takt = current_takt
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout()

        # Título
        title = QLabel("Editar Takt Time")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Descrição
        description = QLabel(
            "Altere informações e estados do takt. O valor será atualizado na interface principal."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666; padding: 10px;")
        description.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(description)

        # Campo de entrada
        input_group = QGroupBox("Contagem do Takt")
        input_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b59b6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #8e44ad;
            }
        """
        )

        input_layout = QFormLayout()
        input_layout.setSpacing(12)
        input_layout.setContentsMargins(20, 20, 20, 20)

        # Label com valor atual
        current_label = QLabel(f"Valor atual: {self.current_takt}")
        current_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        input_layout.addRow("", current_label)

        # Input para novo valor (desabilitado - será implementado no futuro)
        self.takt_input = QLineEdit()
        self.takt_input.setText(str(self.current_takt))
        self.takt_input.setPlaceholderText("Edição manual será implementada em breve")
        self.takt_input.setReadOnly(False)
        self.takt_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px; background-color: #f0f0f0; color: #888;"
        )
        input_layout.addRow("Novo valor:", self.takt_input)

        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # Verificar se a análise está rodando ANTES de criar o botão de edição de estágio
        analysis_running_stage = False
        if self.parent() and hasattr(self.parent(), '_worker_thread'):
            worker_thread_stage = self.parent()._worker_thread
            analysis_running_stage = worker_thread_stage is not None and worker_thread_stage.isRunning()
        
        # Label de status da análise para edição de estágio
        status_stage_label = QLabel()
        if analysis_running_stage:
            status_stage_label.setText("✅ Sistema conectado - Pronto para editar")
            status_stage_label.setStyleSheet(
                "color: #27ae60; font-weight: bold; padding: 5px; "
                "background-color: #d5f4e6; border-radius: 3px;"
            )
        else:
            status_stage_label.setText(
                "⚠️  Atenção: Inicie a análise antes de editar o estágio"
            )
            status_stage_label.setStyleSheet(
                "color: #e67e22; font-weight: bold; padding: 5px; "
                "background-color: #fdebd0; border-radius: 3px;"
            )
        status_stage_label.setAlignment(Qt.AlignCenter)
        status_stage_label.setWordWrap(True)
        main_layout.addWidget(status_stage_label)

        # Botão de Reset
        reset_button_container = QHBoxLayout()
        reset_button_container.addStretch()

        self.edit_takt_stage = QPushButton("🔄 Editar Estágio Contador")
        self.edit_takt_stage.setMinimumHeight(40)
        self.edit_takt_stage.setMinimumWidth(200)
        self.edit_takt_stage.setStyleSheet(
            """
            QPushButton {
                background-color: #e67e22;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #ba4a00;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        )
        
        # Desabilitar botão se análise não está rodando
        self.edit_takt_stage.setEnabled(analysis_running_stage)
        if not analysis_running_stage:
            self.edit_takt_stage.setToolTip(
                "Inicie a análise (botão 'Iniciar Análise' na tela principal) "
                "para habilitar esta função. É necessário conexão MQTT ativa."
            )
        
        self.edit_takt_stage.clicked.connect(self.on_edit_stage)
        reset_button_container.addWidget(self.edit_takt_stage)
        reset_button_container.addStretch()

        main_layout.addLayout(reset_button_container)

        # Grupo de conexão Takt Receptor
        connection_group = QGroupBox("Conexão Takt Receptor")
        connection_group.setStyleSheet(
            """
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
        )

        connection_layout = QFormLayout()
        connection_layout.setSpacing(12)
        connection_layout.setContentsMargins(20, 20, 20, 20)

        # Obter valores atuais de cell e factory
        config = load_config()
        device_config = config.get("device", {})
        current_cell = device_config.get("cell_number", "").strip()
        current_factory = device_config.get("factory", "").strip()
        
        # Calcular device_id atual
        import re
        factory_num = current_factory
        cell_num = current_cell
        current_device_id = f"cost-{factory_num}-{cell_num}"
        
        # Label mostrando device ID atual
        device_id_label = QLabel(f"Device ID atual: {current_device_id}")
        device_id_label.setStyleSheet("color: #7f8c8d; font-style: italic; font-weight: normal;")
        connection_layout.addRow("", device_id_label)

        # Input para número da fábrica
        self.factory_input = QLineEdit()
        self.factory_input.setText(current_factory)
        self.factory_input.setPlaceholderText("Ex: 2")
        self.factory_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        )
        connection_layout.addRow("Fábrica:", self.factory_input)

        # Input para número da célula
        self.cell_input = QLineEdit()
        self.cell_input.setText(current_cell)
        self.cell_input.setPlaceholderText("Ex: 2408")
        self.cell_input.setStyleSheet(
            "padding: 8px; border: 1px solid #ccc; border-radius: 3px;"
        )
        connection_layout.addRow("Célula:", self.cell_input)

        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)

        # Verificar se a análise está rodando
        analysis_running = False
        if self.parent() and hasattr(self.parent(), '_worker_thread'):
            worker_thread = self.parent()._worker_thread
            analysis_running = worker_thread is not None and worker_thread.isRunning()
        
        # Label de status da análise
        status_info_label = QLabel()
        if analysis_running:
            status_info_label.setText("✅ Sistema conectado - Pronto para atualizar")
            status_info_label.setStyleSheet(
                "color: #27ae60; font-weight: bold; padding: 5px; "
                "background-color: #d5f4e6; border-radius: 3px;"
            )
        else:
            status_info_label.setText(
                "⚠️  Atenção: Inicie a análise antes de atualizar a conexão"
            )
            status_info_label.setStyleSheet(
                "color: #e67e22; font-weight: bold; padding: 5px; "
                "background-color: #fdebd0; border-radius: 3px;"
            )
        status_info_label.setAlignment(Qt.AlignCenter)
        status_info_label.setWordWrap(True)
        main_layout.addWidget(status_info_label)

        # Botão de atualização da conexão
        update_connection_container = QHBoxLayout()
        update_connection_container.addStretch()

        self.update_connection_btn = QPushButton("🔗 Atualiza conexao disp. Takt")
        self.update_connection_btn.setMinimumHeight(40)
        self.update_connection_btn.setMinimumWidth(250)
        self.update_connection_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff8c00;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #e67e00;
            }
            QPushButton:pressed {
                background-color: #cc7a00;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        )
        
        # Desabilitar botão se análise não está rodando
        self.update_connection_btn.setEnabled(analysis_running)
        if not analysis_running:
            self.update_connection_btn.setToolTip(
                "Inicie a análise (botão 'Iniciar Análise' na tela principal) "
                "para habilitar esta função. É necessário conexão MQTT ativa."
            )
        
        self.update_connection_btn.clicked.connect(self.update_takt_connection_id)
        update_connection_container.addWidget(self.update_connection_btn)
        update_connection_container.addStretch()

        main_layout.addLayout(update_connection_container)

        # Botões de ação (Salvar/Cancelar)
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Cancel).setText("Fechar")

        # Estilizar botão
        button_box.button(QDialogButtonBox.Cancel).setStyleSheet(
            """
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """
        )

        button_box.rejected.connect(self.reject)

        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def on_edit_stage(self):
        """Atualiza o contador do takt e envia mensagem MQTT"""
        logger.info("[EDIT_STAGE] Atualização do contador de takt solicitado")
        
        # Guard Clause: Verificar se a análise está rodando
        if not self.parent() or not hasattr(self.parent(), '_worker_thread'):
            logger.error("[EDIT_STAGE] ❌ BLOQUEADO: Parent ou worker thread não disponível")
            QMessageBox.warning(
                self,
                "Sistema Não Iniciado",
                "⚠️ A análise não foi iniciada ainda.\n\n"
                "Para editar o estágio do takt, você precisa:\n"
                "1. Fechar este diálogo\n"
                "2. Clicar em '▶️ Iniciar Análise' na tela principal\n"
                "3. Aguardar a conexão MQTT ser estabelecida\n"
                "4. Abrir novamente este diálogo\n\n"
                "A conexão MQTT é necessária para enviar o comando ao ESP32."
            )
            return
        
        worker_thread = self.parent()._worker_thread
        if not worker_thread or not worker_thread.isRunning():
            logger.error("[EDIT_STAGE] ❌ BLOQUEADO: Worker thread não está em execução")
            QMessageBox.warning(
                self,
                "Sistema Não Iniciado",
                "⚠️ A análise não está em execução.\n\n"
                "Para editar o estágio do takt, você precisa:\n"
                "1. Fechar este diálogo\n"
                "2. Clicar em '▶️ Iniciar Análise' na tela principal\n"
                "3. Aguardar a conexão MQTT ser estabelecida\n"
                "4. Abrir novamente este diálogo\n\n"
                "A conexão MQTT é necessária para enviar o comando ao ESP32."
            )
            return
        
        logger.debug("[EDIT_STAGE] ✅ Verificação inicial passou - sistema está pronto")

        # Confirmação do usuário
        reply = QMessageBox.question(
            self,
            "Confirmar Atualização",
            "Tem certeza que deseja atualizar o contador do takt para o valor especificado?\n\n"
            "Esta ação irá:\n"
            f"• Altera o contador para {self.takt_input.text()}\n"
            "• Atualizar a interface\n"
            "• Enviar comando ao ESP32",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.No:
            logger.debug("Edição cancelada pelo usuário")
            return

        if self.takt_input.text() == "3" or self.takt_input.text() == 3:
            logger.info("Bloqueio de edição, tentativa de aplicar nivel 3.")
            QMessageBox.warning(
                self,
                "Ação Bloqueada",
                "Só é possível alterar os estágios entre 0 e 2."
            )
            return

        # Atualiza o valor do takt
        self.takt_value = self.takt_input.text()
        
        logger.info(f"Valor do takt atualizado para {self.takt_value}")

        # Aceita o diálogo e retorna
        self.accept()

    def update_takt_connection_id(self):
        """Atualiza o ID de conexão do dispositivo Takt (célula e fábrica)"""
        logger.info("[UPDATE_ID] Atualização do ID de conexão Takt solicitada")
        
        # Guard Clause: Verificar se a análise está rodando
        if not self.parent() or not hasattr(self.parent(), '_worker_thread'):
            logger.error("[UPDATE_ID] ❌ BLOQUEADO: Parent ou worker thread não disponível")
            QMessageBox.warning(
                self,
                "Sistema Não Iniciado",
                "⚠️ A análise não foi iniciada ainda.\n\n"
                "Para atualizar o ID de conexão, você precisa:\n"
                "1. Fechar este diálogo\n"
                "2. Clicar em '▶️ Iniciar Análise' na tela principal\n"
                "3. Aguardar a conexão MQTT ser estabelecida\n"
                "4. Abrir novamente este diálogo\n\n"
                "A conexão MQTT é necessária para enviar o comando ao ESP32."
            )
            return
        
        worker_thread = self.parent()._worker_thread
        if not worker_thread or not worker_thread.isRunning():
            logger.error("[UPDATE_ID] ❌ BLOQUEADO: Worker thread não está em execução")
            QMessageBox.warning(
                self,
                "Sistema Não Iniciado",
                "⚠️ A análise não está em execução.\n\n"
                "Para atualizar o ID de conexão, você precisa:\n"
                "1. Fechar este diálogo\n"
                "2. Clicar em '▶️ Iniciar Análise' na tela principal\n"
                "3. Aguardar a conexão MQTT ser estabelecida\n"
                "4. Abrir novamente este diálogo\n\n"
                "A conexão MQTT é necessária para enviar o comando ao ESP32."
            )
            return
        
        logger.debug("[UPDATE_ID] ✅ Verificação inicial passou - sistema está pronto")
        
        # Solicitar autenticação - usuário
        username, ok = QInputDialog.getText(
            self, "Autenticação Necessária", "Usuário:", QLineEdit.Normal
        )

        if not ok or not username:
            logger.debug("Autenticação cancelada pelo usuário")
            return

        # Solicitar senha
        password, ok = QInputDialog.getText(
            self, "Autenticação Necessária", "Senha:", QLineEdit.Password
        )

        if not ok or not password:
            logger.debug("Autenticação cancelada pelo usuário")
            return

        # Validar credenciais
        if username != TECH_CONFIG_USER or password != TECH_CONFIG_PASS:
            logger.warning("Tentativa de autenticação falhou para atualização de ID Takt")
            QMessageBox.warning(self, "Acesso Negado", "Usuário ou senha incorretos!")
            return
        
        logger.info("Autenticação bem-sucedida para atualização de ID Takt")
        
        # Obter novos valores dos campos
        new_factory = self.factory_input.text().strip()
        new_cell = self.cell_input.text().strip()
        
        # Validação básica
        if not new_factory or not new_cell:
            logger.warning("Campos de fábrica ou célula vazios")
            QMessageBox.warning(
                self,
                "Campos Obrigatórios",
                "Por favor, preencha os campos de Fábrica e Célula antes de atualizar."
            )
            return
        
        # Calcular novo device_id
        factory_num = new_factory
        cell_num = new_cell
        new_device_id = f"cost-{factory_num}-{cell_num}"
        
        # Confirmação do usuário
        reply = QMessageBox.question(
            self,
            "Confirmar Atualização de ID",
            f"Tem certeza que deseja atualizar o ID de conexão?\n\n"
            f"Fábrica: {new_factory}\n"
            f"Célula: {new_cell}\n"
            f"Novo Device ID: {new_device_id}\n\n"
            "Esta ação irá:\n"
            "• Atualizar a configuração local\n"
            "• Enviar comando ao ESP32\n"
            "• Pode exigir reinicialização da aplicação",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.No:
            logger.debug("Atualização de ID cancelada pelo usuário")
            return

        logger.info(f"[UPDATE_ID] Iniciando processo de atualização - Factory: {new_factory}, Cell: {new_cell}")
        
        # Enviar comando MQTT para atualizar o ESP32 ANTES de salvar
        logger.info("[UPDATE_ID] Passo 1/3: Enviando comando MQTT ao ESP32...")
        mqtt_success = self._send_device_id_update_mqtt(new_factory, new_cell, new_device_id)
        
        # Guard Clause: Só continuar se o envio MQTT foi bem-sucedido
        if not mqtt_success:
            logger.error(f"[UPDATE_ID] ❌ ABORTADO: Falha ao enviar comando MQTT. Configuração NÃO será salva.")
            QMessageBox.critical(
                self,
                "Atualização Cancelada",
                f"Não foi possível enviar o comando ao ESP32.\n\n"
                f"A configuração NÃO foi atualizada para evitar inconsistências.\n\n"
                f"Por favor, verifique:\n"
                f"• Se o sistema de análise está iniciado\n"
                f"• Se a conexão MQTT está ativa\n"
                f"• Se o dispositivo ESP32 está online\n\n"
                f"Tente novamente após verificar estes pontos."
            )
            return
        
        logger.info("[UPDATE_ID] ✅ Passo 1/3: Comando MQTT enviado com sucesso")
        
        # Carregar configuração atual
        logger.info("[UPDATE_ID] Passo 2/3: Salvando configuração local...")
        config = load_config()
        
        # Atualizar valores de device
        if "device" not in config:
            config["device"] = {}
        
        config["device"]["factory"] = new_factory
        config["device"]["cell_number"] = new_cell
        
        # Salvar configuração atualizada
        try:
            save_config(config)
            logger.info(f"[UPDATE_ID] ✅ Passo 2/3: Configuração salva - Factory: {new_factory}, Cell: {new_cell}")
        except Exception as e:
            logger.error(f"[UPDATE_ID] ❌ Erro ao salvar configuração: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erro ao Salvar",
                f"ATENÇÃO: O comando foi enviado ao ESP32, mas não foi possível salvar a configuração local!\n\n"
                f"Erro: {e}\n\n"
                f"Recomenda-se reiniciar a aplicação e tentar novamente."
            )
            return
        
        # Atualizar a UI do parent se disponível
        logger.info("[UPDATE_ID] Passo 3/3: Atualizando interface...")
        if self.parent() and hasattr(self.parent(), '_load'):
            self.parent()._load()
            logger.debug("[UPDATE_ID] Interface do parent atualizada")
        
        logger.info(f"[UPDATE_ID] ✅ CONCLUÍDO: ID atualizado com sucesso para {new_device_id}")
        
        QMessageBox.information(
            self,
            "ID Atualizado com Sucesso",
            f"✅ ID de conexão atualizado com sucesso!\n\n"
            f"Novo Device ID: {new_device_id}\n"
            f"Fábrica: {new_factory}\n"
            f"Célula: {new_cell}\n\n"
            f"✅ Comando enviado e confirmado pelo ESP32\n"
            f"✅ Configuração salva localmente\n\n"
            f"Considere reiniciar a aplicação para garantir que todas as conexões sejam atualizadas."
        )
    
    def _send_device_id_update_mqtt(self, factory: str, cell: str, new_device_id: str) -> bool:
        """Envia mensagem MQTT de atualização do device_id para o ESP32
        
        IMPORTANTE: A mensagem é enviada para o device_id ANTIGO (atual na config),
        pois o ESP32 ainda está inscrito nesse tópico. O novo device_id é enviado
        dentro da mensagem para que o ESP32 se reconfigure.
        
        Returns:
            bool: True se a mensagem foi enviada com sucesso, False caso contrário
        """
        # Obter o device_id ATUAL (antigo) da configuração - é para ele que devemos enviar
        config = load_config()
        device_config = config.get("device", {})
        current_factory = device_config.get("factory", "").strip()
        current_cell = device_config.get("cell_number", "").strip()
        old_device_id = f"cost-{current_factory}-{current_cell}"
        
        logger.info(f"[MQTT_SEND] Iniciando envio de atualização de device_id")
        logger.info(f"[MQTT_SEND] Device ID ANTIGO (destino): {old_device_id}")
        logger.info(f"[MQTT_SEND] Device ID NOVO (na mensagem): {new_device_id}")
        logger.debug(f"[MQTT_SEND] Parâmetros - Factory: {factory}, Cell: {cell}")
        
        try:
            import json
            from datetime import datetime

            # Cria a mensagem seguindo o padrão de device_config
            # O novo device_id vai DENTRO da mensagem para o ESP32 se reconfigurar
            message = {
                "event": "device_config",
                "message": "update_device_id",
                "factory": factory,
                "cell_number": cell,
                "device_id": new_device_id  # Novo ID para o ESP32 usar
            }
            logger.debug(f"[MQTT_SEND] Mensagem preparada: {message}")

            # Guard Clause 1: Verificar se parent existe
            if not self.parent():
                logger.error("[MQTT_SEND] ❌ FALHA: Parent window não disponível")
                QMessageBox.warning(
                    self,
                    "Erro de Sistema",
                    "Janela principal não está disponível.\n\n"
                    "Por favor, tente novamente ou reinicie a aplicação.",
                )
                return False
            
            # Guard Clause 2: Verificar se parent tem _worker_thread
            if not hasattr(self.parent(), '_worker_thread'):
                logger.error("[MQTT_SEND] ❌ FALHA: Worker thread não existe no parent")
                QMessageBox.warning(
                    self,
                    "Sistema Não Iniciado",
                    "O sistema de análise não foi iniciado ainda.\n\n"
                    "Por favor, inicie a análise antes de atualizar o ID de conexão.",
                )
                return False
            
            worker_thread = self.parent()._worker_thread
            
            # Guard Clause 3: Verificar se worker thread está rodando
            if not worker_thread or not worker_thread.isRunning():
                logger.error("[MQTT_SEND] ❌ FALHA: Worker thread não está em execução")
                QMessageBox.warning(
                    self,
                    "Sistema Não Iniciado",
                    "O sistema de análise não está em execução.\n\n"
                    "Por favor, inicie a análise antes de atualizar o ID de conexão.",
                )
                return False
            
            logger.debug("[MQTT_SEND] Worker thread encontrada e em execução")
            
            # Guard Clause 4: Verificar se mqtt_manager existe
            mqtt_manager = getattr(worker_thread, "_mqtt_manager", None)
            if not mqtt_manager:
                logger.error("[MQTT_SEND] ❌ FALHA: MQTT Manager não encontrado no worker thread")
                QMessageBox.warning(
                    self,
                    "MQTT Não Configurado",
                    "O gerenciador MQTT não está disponível.\n\n"
                    "Por favor, verifique a configuração e reinicie a análise.",
                )
                return False
            
            logger.debug("[MQTT_SEND] MQTT Manager encontrado")
            
            # Guard Clause 5: Verificar se está conectado
            if not mqtt_manager._connected:
                logger.error("[MQTT_SEND] ❌ FALHA: MQTT Manager não está conectado ao broker")
                QMessageBox.warning(
                    self,
                    "MQTT Desconectado",
                    "O sistema não está conectado ao broker MQTT.\n\n"
                    "Por favor, verifique a conexão de rede e reinicie a análise.",
                )
                return False
            
            logger.info(f"[MQTT_SEND] ✅ MQTT conectado. Enviando comando para device_id ANTIGO: {old_device_id}")
            
            # Tentar enviar o comando para o device_id ANTIGO (onde o ESP32 está inscrito)
            success = mqtt_manager.publish_command(old_device_id, message)

            if success:
                logger.info(f"[MQTT_SEND] ✅ SUCESSO: Mensagem MQTT enviada para {old_device_id} (ESP32 receberá novo ID: {new_device_id})")
                return True
            else:
                logger.error(f"[MQTT_SEND] ❌ FALHA: publish_command retornou False para {old_device_id}")
                QMessageBox.warning(
                    self,
                    "Erro ao Enviar",
                    "Não foi possível enviar o comando ao ESP32.\n\n"
                    "Verifique a conexão MQTT e tente novamente.",
                )
                return False

        except Exception as e:
            logger.error(f"[MQTT_SEND] ❌ EXCEÇÃO: Erro inesperado ao enviar mensagem MQTT: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Erro de Comunicação",
                f"Erro ao enviar comando MQTT:\n{e}\n\n"
                f"Por favor, verifique a conexão e tente novamente.",
            )
            return False
    
    def get_takt_value(self):
        """Retorna o valor do takt definido"""
        return getattr(self, "takt_value", None)


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
        self.takt_timeout_sec = (
            40  # Tempo maximo sem resposta antes de considerar inativa
        )
        self.last_takt_time_count = 0

        # Estado de inicialização e segurança
        self._model_loaded = False
        self._mqtt_connected = False
        self._initialization_thread = None

        # Controle de aviso de dispositivo desconectado (evita spam)
        self._last_device_warning_time = None
        self._device_warning_cooldown = 30  # segundos entre avisos

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

        self.edit_takt_btn = QPushButton("Editar Takt")
        self.edit_takt_btn.setMinimumHeight(45)
        self.edit_takt_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
            }
        """
        )
        self.edit_takt_btn.clicked.connect(self.on_edit_takt)
        btn_layout.addWidget(self.edit_takt_btn)

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

        # Botão de reconectar ao broker MQTT
        self.reconnect_mqtt_btn = QPushButton("🔄 Reconectar MQTT")
        self.reconnect_mqtt_btn.setFixedHeight(30)
        self.reconnect_mqtt_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        )
        self.reconnect_mqtt_btn.setEnabled(False)  # Desabilitado inicialmente
        self.reconnect_mqtt_btn.setToolTip(
            "Reconectar ao broker MQTT (disponível apenas quando desconectado)"
        )
        self.reconnect_mqtt_btn.clicked.connect(self.on_reconnect_mqtt)
        init_status_layout.addWidget(self.reconnect_mqtt_btn)

        layout.addLayout(init_status_layout)

        # Botão para controlar Worker MQTT isoladamente (canto inferior esquerdo)
        worker_control_layout = QHBoxLayout()
        
        self.worker_mqtt_btn = QPushButton("🔌 Iniciar Worker MQTT")
        self.worker_mqtt_btn.setFixedHeight(35)
        self.worker_mqtt_btn.setFixedWidth(180)
        self.worker_mqtt_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #16a085;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
            QPushButton:pressed {
                background-color: #117a65;
            }
        """
        )
        self.worker_mqtt_btn.setToolTip(
            "Inicia/Para o Worker MQTT sem necessidade de iniciar a análise completa"
        )
        self.worker_mqtt_btn.clicked.connect(self.on_toggle_worker_mqtt)
        worker_control_layout.addWidget(self.worker_mqtt_btn)
        worker_control_layout.addStretch()
        
        layout.addLayout(worker_control_layout)

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

    def on_edit_takt(self):
        # Abre o diálogo de edição do takt
        dialog = EditTaktDialog(self, self.last_takt_time_count)
        if dialog.exec_() == QDialog.Accepted:
            new_takt_value = dialog.get_takt_value()

            # Verifica se um valor foi retornado (usuário clicou em alterar takt)
            if new_takt_value is not None:
                logger.info(f"Alteração do takt solicitado. Novo valor: {new_takt_value}")

                # Atualiza o valor na UI
                self.last_takt_time_count = new_takt_value
                self.status_takt.setText(str(new_takt_value))

                # Cancela o timer de reset automático se estiver ativo
                if (
                    hasattr(self, "_takt_reset_timer")
                    and self._takt_reset_timer.isActive()
                ):
                    self._takt_reset_timer.stop()
                    logger.debug("Timer de reset automático cancelado")

                # Envia mensagem MQTT para o ESP32
                self._send_takt_edit_stage_mqtt(new_takt_value)

                QMessageBox.information(
                    self,
                    "Takt Resetado",
                    f"Contador resetado para: {new_takt_value}\n\nComando enviado ao ESP32.",
                )

    def _send_takt_edit_stage_mqtt(self, takt_count: int):
        """Envia mensagem MQTT de edição do estágio do takt para o ESP32"""
        try:
            import json
            from datetime import datetime

            # Obtém o device_id da configuração
            cfg = load_config()
            device = cfg.get("device", {})
            cell_number = device.get("cell_number", "").strip()
            factory = device.get("factory", "").strip()

            factory_num = factory
            cell_num = cell_number
            device_id = f"cost-{factory_num}-{cell_num}"

            # Cria a mensagem
            message = {
                "event": "device_config",
                "message": "update_config",
                "takt_count": takt_count
            }

            # Verifica se há worker thread rodando com conexão MQTT
            if self._worker_thread and self._worker_thread.isRunning():
                mqtt_manager = getattr(self._worker_thread, "_mqtt_manager", None)
                if mqtt_manager and mqtt_manager._connected:
                    logger.info(
                        f"Enviando reset do takt via MQTT para {device_id}: {message}"
                    )

                    # Usa publish_command do MQTTManager
                    success = mqtt_manager.publish_command(device_id, message)

                    if success:
                        logger.info("Mensagem MQTT de reset enviada com sucesso")
                    else:
                        logger.warning("Falha ao enviar mensagem MQTT de reset")
                        QMessageBox.warning(
                            self,
                            "Erro ao Enviar",
                            "Não foi possível enviar o comando ao ESP32.\n\n"
                            "Verifique a conexão MQTT.",
                        )
                else:
                    logger.warning(
                        "MQTT Manager não está conectado. Mensagem não enviada."
                    )
                    QMessageBox.warning(
                        self,
                        "MQTT Desconectado",
                        "Não foi possível enviar o comando ao ESP32.\n\n"
                        "O sistema MQTT não está conectado.\n"
                        "Inicie a análise primeiro para estabelecer conexão.",
                    )
            else:
                logger.warning(
                    "Worker thread não está rodando. Mensagem MQTT não enviada."
                )
                QMessageBox.warning(
                    self,
                    "Sistema Parado",
                    "Não foi possível enviar o comando ao ESP32.\n\n"
                    "O sistema de análise não está rodando.\n"
                    "Inicie a análise primeiro para estabelecer conexão.",
                )

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem MQTT de reset: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Erro ao Enviar Comando",
                f"Erro ao enviar comando de reset ao ESP32:\n{e}",
            )

    def on_reconnect_mqtt(self):
        """Tenta reconectar ao broker MQTT"""
        logger.info("=== Tentando reconectar ao broker MQTT ===")

        # Desabilita o botão durante a tentativa de reconexão
        self.reconnect_mqtt_btn.setEnabled(False)
        self.reconnect_mqtt_btn.setText("🔄 Conectando...")

        # Atualiza status visual
        self.mqtt_status_label.setText("🟡 MQTT: Reconectando...")
        self.mqtt_status_label.setStyleSheet(
            "padding: 5px; font-size: 10pt; color: #f39c12;"
        )

        # Inicia thread de reconexão
        if (
            self._initialization_thread is None
            or not self._initialization_thread.isRunning()
        ):
            logger.debug("Iniciando InitializationWorker thread para reconexão MQTT")
            self._initialization_thread = InitializationWorker(self, check_model=False)
            self._initialization_thread.status_update.connect(
                self._on_initialization_update
            )
            self._initialization_thread.start()
        else:
            logger.warning("InitializationWorker thread já está em execução")
            # Reabilita o botão se não conseguiu iniciar a thread
            self.reconnect_mqtt_btn.setEnabled(True)
            self.reconnect_mqtt_btn.setText("🔄 Reconectar MQTT")

    def on_toggle_worker_mqtt(self):
        """Inicia ou para o Worker MQTT isoladamente"""
        if self._worker_thread is not None and self._worker_thread.isRunning():
            # Parar o worker
            logger.info("[WORKER_MQTT] Solicitando parada do Worker MQTT")
            
            # Verificar se a análise está rodando
            if self._analysis_running:
                logger.warning("[WORKER_MQTT] ⚠️ Análise está em execução - não pode parar o worker")
                QMessageBox.warning(
                    self,
                    "Análise em Execução",
                    "⚠️ Não é possível parar o Worker MQTT enquanto a análise está em execução.\n\n"
                    "Para parar o worker:\n"
                    "1. Pare a análise primeiro (botão '⏸️ Parar Análise')\n"
                    "2. Depois pare o Worker MQTT"
                )
                return
            
            reply = QMessageBox.question(
                self,
                "Confirmar Parada do Worker",
                "Tem certeza que deseja parar o Worker MQTT?\n\n"
                "Isso irá desconectar do broker MQTT e impedir:\n"
                "• Envio de comandos ao ESP32\n"
                "• Atualização de ID de conexão\n"
                "• Edição de estágios do takt\n\n"
                "Você pode reiniciá-lo a qualquer momento.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            
            if reply == QMessageBox.No:
                logger.debug("[WORKER_MQTT] Parada do worker cancelada pelo usuário")
                return
            
            self.worker_mqtt_btn.setEnabled(False)
            self.worker_mqtt_btn.setText("⏳ Parando...")
            
            try:
                self._worker_thread.stop()
                self._worker_thread.wait(5000)  # aguarda até 5s
                logger.info("[WORKER_MQTT] ✅ Worker MQTT parado com sucesso")
                
                # Atualizar status MQTT
                self.mqtt_status_label.setText("🔴 MQTT: Desconectado")
                self.mqtt_status_label.setStyleSheet(
                    "padding: 5px; font-size: 10pt; color: #e74c3c;"
                )
                
                QMessageBox.information(
                    self,
                    "Worker Parado",
                    "✅ Worker MQTT foi parado com sucesso.\n\n"
                    "Você pode reiniciá-lo clicando no botão 'Iniciar Worker MQTT'."
                )
            except Exception as e:
                logger.error(f"[WORKER_MQTT] ❌ Erro ao parar worker: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Erro ao Parar Worker",
                    f"Ocorreu um erro ao parar o Worker MQTT:\n{e}\n\n"
                    f"Tente reiniciar a aplicação."
                )
            finally:
                self._update_worker_button_state()
        else:
            # Iniciar o worker
            logger.info("[WORKER_MQTT] Solicitando início do Worker MQTT")
            
            self.worker_mqtt_btn.setEnabled(False)
            self.worker_mqtt_btn.setText("⏳ Iniciando...")
            
            try:
                logger.debug("[WORKER_MQTT] Criando e iniciando AsyncWorker thread")
                self._worker_thread = AsyncWorker(self)
                self._worker_thread.set_device_status_callback(
                    self._on_device_status_changed
                )
                self._worker_thread.status_update.connect(self.on_worker_status_update)
                self._worker_thread.start()
                logger.info("[WORKER_MQTT] ✅ Worker MQTT iniciado com sucesso")
                
                QMessageBox.information(
                    self,
                    "Worker Iniciado",
                    "✅ Worker MQTT foi iniciado com sucesso.\n\n"
                    "Aguarde alguns segundos para a conexão ser estabelecida.\n"
                    "O status será atualizado automaticamente."
                )
            except Exception as e:
                logger.error(f"[WORKER_MQTT] ❌ Erro ao iniciar worker: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Erro ao Iniciar Worker",
                    f"Ocorreu um erro ao iniciar o Worker MQTT:\n{e}\n\n"
                    f"Verifique as configurações e tente novamente."
                )
            finally:
                self._update_worker_button_state()
    
    def _update_worker_button_state(self):
        """Atualiza o estado visual do botão do Worker MQTT"""
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self.worker_mqtt_btn.setEnabled(True)
            self.worker_mqtt_btn.setText("🔌 Parar Worker MQTT")
            self.worker_mqtt_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    padding: 5px 15px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """
            )
            self.worker_mqtt_btn.setToolTip(
                "Clique para parar o Worker MQTT (não disponível durante análise)"
            )
            logger.debug("[WORKER_MQTT] Botão atualizado - Estado: RODANDO (vermelho)")
        else:
            self.worker_mqtt_btn.setEnabled(True)
            self.worker_mqtt_btn.setText("🔌 Iniciar Worker MQTT")
            self.worker_mqtt_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #16a085;
                    color: white;
                    padding: 5px 15px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #138d75;
                }
                QPushButton:pressed {
                    background-color: #117a65;
                }
            """
            )
            self.worker_mqtt_btn.setToolTip(
                "Inicia o Worker MQTT sem necessidade de iniciar a análise completa"
            )
            logger.debug("[WORKER_MQTT] Botão atualizado - Estado: PARADO (verde)")

    def _check_prerequisites(self):
        """Verifica se modelo e MQTT estão disponíveis antes de habilitar análise"""
        logger.info("=== Iniciando verificação de pré-requisitos ===")
        self.start_stop_btn.setEnabled(False)
        self.start_stop_btn.setText("Verificando Sistema...")

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

        elif event == "model_error" and not self._model_loaded:
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

            # Desabilita o botão de reconexão quando conectado
            self.reconnect_mqtt_btn.setEnabled(False)
            self.reconnect_mqtt_btn.setText("🔄 Reconectar MQTT")
            self.reconnect_mqtt_btn.setToolTip(
                "Reconectar ao broker MQTT (disponível apenas quando desconectado)"
            )

        elif event == "mqtt_error":
            self._mqtt_connected = False
            error_msg = data.get("error", "Erro desconhecido")
            logger.error(f"✗ Erro na conexão MQTT: {error_msg}")
            self.mqtt_status_label.setText(f"🔴 MQTT: Erro")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c;"
            )

            # Habilita o botão de reconexão quando desconectado
            self.reconnect_mqtt_btn.setEnabled(True)
            self.reconnect_mqtt_btn.setText("🔄 Reconectar MQTT")
            self.reconnect_mqtt_btn.setToolTip(
                "Clique para tentar reconectar ao broker MQTT"
            )

            # Mensagem de erro mais detalhada
            cfg = load_config()
            tech = cfg.get("tech", {})
            mqtt_host = tech.get("mqtt_host", "não configurado")

            QMessageBox.warning(
                self,
                "Erro na Conexão MQTT",
                f"Falha ao conectar ao broker MQTT:\n\n"
                f"Host: {mqtt_host}\n"
                f"Erro: {error_msg}\n\n"
                f"Verifique:\n"
                f"• Se o broker MQTT está rodando\n"
                f"• Se o endereço está correto nas configurações\n"
                f"• Se há conectividade de rede\n\n"
                f"Configure corretamente ou use o botão 'Reconectar MQTT'.",
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
            self.esp32_status_label.setToolTip(
                f"Dispositivo {device_id} está online e enviando heartbeats"
            )
        else:
            self.esp32_status_label.setText(f"🔴 ESP32: Desconectado ({device_id})")
            self.esp32_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #e74c3c; font-weight: bold;"
            )
            self.esp32_status_label.setToolTip(
                f"Dispositivo {device_id} está offline ou não responde"
            )
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
            # Verificar se worker já não está rodando para evitar múltiplas instâncias
            if self._worker_thread is not None and self._worker_thread.isRunning():
                logger.warning("⚠️ AsyncWorker thread já está em execução - não será criado novamente")
                QMessageBox.information(
                    self,
                    "Worker Já Iniciado",
                    "O Worker MQTT já está em execução.\n\n"
                    "A análise será iniciada usando o worker existente."
                )
            else:
                logger.debug("Criando e iniciando AsyncWorker thread")
                self._worker_thread = AsyncWorker(self)
                # Conecta o sinal do worker para atualizar o label na UI
                self._worker_thread.set_device_status_callback(
                    self._on_device_status_changed
                )
                self._worker_thread.status_update.connect(self.on_worker_status_update)
                self._worker_thread.start()
                logger.info("AsyncWorker thread iniciado para análise")
                
                # Atualizar botão do worker MQTT
                self._update_worker_button_state()
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
            # NOTA: Não para o worker aqui se foi iniciado isoladamente
            # O worker continua rodando para permitir comandos MQTT sem análise
            logger.info("Análise parada - Worker MQTT continua rodando para comandos")

    def on_worker_status_update(self, data: dict):
        event = data.get("event")
        # logger.debug(f"Worker status update: {event} - {data}")

        if event == "connected":
            logger.info("✅ Conexão MQTT estabelecida pelo AsyncWorker")
            self.mqtt_status_label.setText("🟢 MQTT: Conectado")
            self.mqtt_status_label.setStyleSheet(
                "padding: 5px; font-size: 10pt; color: #27ae60;"
            )

            # Desabilita o botão de reconexão quando conectado
            self.reconnect_mqtt_btn.setEnabled(False)
            self.reconnect_mqtt_btn.setText("🔄 Reconectar MQTT")
            self.reconnect_mqtt_btn.setToolTip(
                "Reconectar ao broker MQTT (disponível apenas quando desconectado)"
            )
            
            # Atualizar botão do Worker MQTT
            self._update_worker_button_state()

            # Atualizar status do ESP32 para "aguardando" APENAS se ainda estiver no estado inicial
            if (
                "Aguardando..." in self.esp32_status_label.text()
                or "⚪" in self.esp32_status_label.text()
            ):
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

            # Habilita o botão de reconexão
            self.reconnect_mqtt_btn.setEnabled(True)
            self.reconnect_mqtt_btn.setText("🔄 Reconectar MQTT")
            self.reconnect_mqtt_btn.setToolTip(
                "Clique para tentar reconectar ao broker MQTT"
            )
            
            # Atualizar botão do Worker MQTT
            self._update_worker_button_state()

            # Para a análise ANTES de mostrar o dialog para evitar loop
            if self._analysis_running:
                logger.warning("Parando análise devido a erro na conexão MQTT")
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
                self.status_label.setText("⏸️ Parado - Erro MQTT")
                self.status_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #e74c3c; padding: 15px;"
                )
                self.configure_btn.setEnabled(True)
                # Para o worker thread
                if self._worker_thread and self._worker_thread.isRunning():
                    logger.debug("Parando AsyncWorker thread devido a erro MQTT")
                    self._worker_thread.stop()

            # Mostra o erro apenas uma vez
            QMessageBox.critical(
                self,
                "Erro na Conexão MQTT",
                f"Falha ao conectar ao broker MQTT:\n{error_msg}\n\nVerifique:\n• Se o broker está rodando\n• Se o endereço está correto\n• Se há conectividade de rede\n\nA análise foi interrompida.\n\nUse o botão 'Reconectar MQTT' para tentar novamente.",
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
            device_connected = data.get("device_connected", False)

            logger.info(
                f"Takt detectado! Etapa: {takt_number}/3 (ESP32: {'conectado' if device_connected else 'desconectado'})"
            )
            self.takt_screen_working = True

            # Atualiza status com cor diferente baseado na conexão do ESP32
            if device_connected:
                self.status_label.setText("Analisando (ESP32 ON)")
                self.status_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #27ae60; padding: 15px;"
                )
            else:
                self.status_label.setText("Analisando (ESP32 OFF)")
                self.status_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #f39c12; padding: 15px;"
                )

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

        elif event == "device_disconnected":
            device_id = data.get("device_id", "")
            message = data.get("message", "")
            takt_detected = data.get("takt_detected", False)

            logger.warning(f"{message}")

            if takt_detected:
                self.status_label.setText(f"Takt detectado mas ESP32 desconectado!")
                self.status_label.setStyleSheet(
                    "font-size: 14pt; font-weight: bold; color: #f39c12; padding: 15px;"
                )

                # Verifica cooldown antes de mostrar dialog (evita spam)
                current_time = time.time()
                should_show_warning = False

                if self._last_device_warning_time is None:
                    # Primeira vez, mostra
                    should_show_warning = True
                elif (
                    current_time - self._last_device_warning_time
                ) >= self._device_warning_cooldown:
                    # Já passou tempo suficiente desde último aviso
                    should_show_warning = True
                else:
                    # Ainda em cooldown
                    time_remaining = self._device_warning_cooldown - (
                        current_time - self._last_device_warning_time
                    )
                    logger.debug(
                        f"Aviso de dispositivo desconectado em cooldown. "
                        f"Próximo aviso em {time_remaining:.0f}s"
                    )

                if should_show_warning:
                    self._last_device_warning_time = current_time
                    # Exibe notificação visual não-bloqueante
                    QTimer.singleShot(
                        0, lambda: self._show_device_disconnected_warning(device_id)
                    )

    def _reset_takt_counter(self):
        """Reseta o contador de takt tanto na UI quanto na variável interna"""
        logger.info("Resetando contador de takt para 0")
        self.last_takt_time_count = 0
        self.status_takt.setText("0")

    def _show_device_disconnected_warning(self, device_id: str):
        """Exibe aviso de dispositivo desconectado sem bloquear a UI"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("ESP32 Desconectado")
        msg.setText(f"Dispositivo ESP32 não está conectado!")
        msg.setInformativeText(
            f"Dispositivo: {device_id}\n\n"
            f"Um takt foi detectado, mas a mensagem NÃO foi enviada "
            f"porque o ESP32 não está conectado ao broker MQTT.\n\n"
            f"Verifique:\n"
            f"• ESP32 está ligado?\n"
            f"• Está conectado ao WiFi?\n"
            f"• Consegue acessar o broker MQTT?\n"
            f"• Está enviando heartbeats?\n\n"
            f"A análise continuará rodando."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(
            """
            QMessageBox {
                background-color: #fff3cd;
            }
            QLabel {
                color: #856404;
            }
        """
        )
        msg.exec_()

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
                tracker = None
                stopper = None

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

                    factory_num = factory
                    cell_num = cell_number
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

                    else:
                        logger.error("Falha ao conectar ao broker MQTT")
                        on_event(
                            "connection_error",
                            {"error": "Falha ao conectar ao broker MQTT"},
                        )
                        return
                except Exception as e:
                    logger.error(
                        f"Erro ao estabelecer conexão MQTT: {e}", exc_info=True
                    )
                    on_event("connection_error", {"error": str(e)})
                    return

                async def stop_waiter():
                    await self._stop.wait()
                    # Cancel the tracker when stop requested
                    if tracker:
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
                    if tracker and not tracker.done():
                        tracker.cancel()
                        try:
                            await tracker
                        except asyncio.CancelledError:
                            pass
                    # Cancel stopper too
                    if stopper and not stopper.done():
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

    def __init__(self, parent=None, check_model=True):
        super().__init__(parent)
        self.check_model = check_model
        logger.debug(f"InitializationWorker criado (check_model={check_model})")

    def run(self):
        """Verifica se modelo YOLO e conexão MQTT estão disponíveis"""
        import os

        logger.info("=== InitializationWorker: Iniciando verificações ===")

        # 1. Verificar Modelo YOLO (apenas se check_model=True)
        if self.check_model:
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
        else:
            logger.debug("Verificação de modelo pulada (check_model=False)")

        # 2. Verificar Conexão MQTT
        self.status_update.emit({"event": "mqtt_check_start"})

        try:
            cfg = load_config()
            tech_config = cfg.get("tech", {})
            mqtt_host = tech_config.get("mqtt_host", "").strip()
            mqtt_user = tech_config.get("mqtt_user", "").strip()
            mqtt_pass = tech_config.get("mqtt_pass", "").strip()

            # Se não houver configuração MQTT, avisa mas permite continuar
            if not mqtt_host:
                logger.warning("Configuração MQTT não definida")
                self.status_update.emit(
                    {
                        "event": "mqtt_error",
                        "error": "Host MQTT não configurado. Configure nas configurações técnicas.",
                    }
                )
                return

            logger.debug(f"Testando conexão MQTT com: {mqtt_host}")

            # Testa conexão MQTT de verdade
            from mqtt_manager import MQTTManager

            test_mqtt = MQTTManager(
                broker=mqtt_host,
                port=1883,
                username=mqtt_user,
                password=mqtt_pass,
                timeout_seconds=10,
            )

            # Tenta conectar com timeout reduzido
            if test_mqtt.connect(timeout=5):
                logger.info(f"Conexão MQTT estabelecida com sucesso: {mqtt_host}")
                self.status_update.emit(
                    {"event": "mqtt_connected", "url": f"{mqtt_host}:1883"}
                )
                test_mqtt.disconnect()
            else:
                raise ConnectionError("Falha ao conectar ao broker MQTT")

        except Exception as e:
            logger.error(f"Erro ao verificar conexão MQTT: {e}", exc_info=True)
            self.status_update.emit({"event": "mqtt_error", "error": str(e)})
            return

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
