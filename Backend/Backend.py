from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import json
import sqlite3
import numpy as np

app = Flask(__name__)
CORS(app)

# Diretório de uploads
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Arquivo de configuração e banco de dados
CONFIG_FILE = "form_config.json"
DB_FILE = "form_data.db"

# Inicializa o banco de dados
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS form_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data JSON NOT NULL
        )
        """)
        conn.commit()

# Função para carregar e salvar JSON
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        with open(file, "w") as f:
            json.dump(default, f)
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Rota para obter a configuração das colunas
@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    if request.method == "GET":
        config = load_json(CONFIG_FILE, {"fields": []})
        return jsonify(config)
    
    elif request.method == "POST":
        try:
            config = request.json
            save_json(CONFIG_FILE, config)
            return jsonify({"message": "Configuração salva com sucesso!"})
        except Exception as e:
            print(f"Erro ao salvar configuração: {str(e)}")
            return jsonify({"error": f"Erro ao salvar configuração: {str(e)}"}), 500

# Rota para listar dados salvos no banco de dados
@app.route("/api/data", methods=["GET"])
def list_form_data():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM form_responses")
            rows = cursor.fetchall()

            # Substituir NaN por null no JSON retornado
            data = [{"id": row[0], "data": json.loads(row[1].replace("NaN", "null"))} for row in rows]

        return jsonify(data)
    except Exception as e:
        print(f"Erro ao listar dados: {str(e)}")
        return jsonify({"error": f"Erro ao listar dados: {str(e)}"}), 500

# Rota para salvar dados do formulário no banco de dados
@app.route("/api/data", methods=["POST"])
def save_form_data():
    try:
        data = request.json

        # Substituir NaN por None antes de salvar
        data = {key: (value if value is not None else None) for key, value in data.items()}

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO form_responses (data) VALUES (?)", [json.dumps(data)])
            conn.commit()
        return jsonify({"message": "Dados salvos com sucesso!"})
    except Exception as e:
        print(f"Erro ao salvar dados do formulário: {str(e)}")
        return jsonify({"error": f"Erro ao salvar dados do formulário: {str(e)}"}), 500

# Rota para upload de arquivos CSV
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Apenas arquivos .csv são suportados"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    try:
        # Ler o arquivo CSV com pandas
        data = pd.read_csv(file_path, encoding="utf-8")

        # Substituir NaN por None para compatibilidade com JSON
        data = data.replace({np.nan: None})
        data_records = data.to_dict(orient="records")  # Converter para lista de dicionários

        # Salvar cada linha como entrada no banco de dados
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for record in data_records:
                cursor.execute("INSERT INTO form_responses (data) VALUES (?)", [json.dumps(record)])
            conn.commit()

        print(f"Arquivo carregado com sucesso. Dados: {data_records}")
        return jsonify({"message": "Arquivo carregado com sucesso!", "data": data_records})
    except pd.errors.EmptyDataError:
        print("Erro: Arquivo CSV vazio.")
        return jsonify({"error": "O arquivo CSV está vazio."}), 400
    except pd.errors.ParserError as e:
        print(f"Erro de parsing no arquivo CSV: {str(e)}")
        return jsonify({"error": f"Erro ao processar o arquivo CSV: {str(e)}"}), 400
    except Exception as e:
        print(f"Erro ao processar o arquivo CSV: {str(e)}")
        return jsonify({"error": f"Erro ao processar o arquivo: {str(e)}"}), 500

# Inicializa o banco de dados ao iniciar o app
if __name__ == "__main__":
    init_db()
    app.run(debug=True)