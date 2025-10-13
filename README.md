# Detecçao de Takt Time 00:00:00

## -- WINDOWS --

1. **Instale o Tesseract OCR**

   - [Link de instalaçãoo para Windows](https://github.com/UB-Mannheim/tesseract/wiki)
   - https://github.com/UB-Mannheim/tesseract/wiki

2. **Instale as depend�ncias**

   ```sh
   pip install -r requirements.txt -y
   ```

3. **Execute o programa**
   ```sh
   python takt_time.py
   ```

## -- LINUX --

1. **Instale o Tesseract OCR**

   - [Link de instalaçãoo para Windows](https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.3.4.tar.gz)
   - https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.3.4.tar.gz

   - 1.1.

   ```sh
   tar xzf tesseract-ocr-3.02.02.tar.gz
   cd tesseract-ocr
   sudo ./autogen.sh
   sudo ./configure
   sudo make
   sudo make install
   sudo ldconfig
   ```

2. **Instale as dependências**

   ```sh
   pip install -r requirements.txt -y
   ```

3. **Execute o programa**
   ```sh
   python takt_time.py
   ```
