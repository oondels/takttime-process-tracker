APP_DIR="/opt/dass_apps/takttime-process-tracker"
cd "$APP_DIR || exit 1"

python app.py 2>&1 | tee -a logs/app.log

if [ $? -n0 0 ]; then
	zenity --error --text="Erro ao iniciar app Takt" --width=400
fi
