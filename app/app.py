import json
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
from PyQt5.QtCore import Qt


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

		self._build_ui()
		self._load()

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
			self.set_inputs_enabled(True)
			self.configure_btn.setText("Salvar Configuração")
		else:
			# Salva e desabilita edição
			data = {
				"cell_number": self.cell_input.text().strip(),
				"factory": self.factory_input.text().strip(),
				"cell_leader": self.leader_input.text().strip(),
			}
			try:
				save_config(data)
				QMessageBox.information(self, "Configuração", "Configuração salva com sucesso.")
			except Exception as e:
				QMessageBox.critical(self, "Erro", f"Falha ao salvar configuração: {e}")
			self.set_inputs_enabled(False)
			self.configure_btn.setText("Configurar")

	def on_start_stop(self):
		if not self._analysis_running:
			# Start analysis: check that config exists
			cfg = load_config()
			if not (cfg.get("cell_number") and cfg.get("factory") and cfg.get("cell_leader")):
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
			# Aqui você acionaria o processo de análise real (thread/process)
		else:
			# parar
			self._analysis_running = False
			self.start_stop_btn.setText("Iniciar Análise")
			self.status_label.setText("Parado")


def main():
	app = QApplication([])
	window = MainWindow()
	window.show()
	app.exec()


if __name__ == "__main__":
	main()