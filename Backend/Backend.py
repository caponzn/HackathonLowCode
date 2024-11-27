from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import json
import sqlite3
import numpy as np

app = Flask(__name__)

# Permitir CORS para o frontend em http://127.0.0.1:5501
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5501"}})

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

# Função para validar o arquivo CSV com base na configuração
def validate_csv(file_path):
    # Carregar a configuração das colunas
    config = load_json(CONFIG_FILE, {"fields": []})
    fields = config.get("fields", [])

    # Ler o arquivo CSV
    try:
        data = pd.read_csv(file_path, encoding="utf-8")
    except Exception as e:
        return False, f"Erro ao ler o arquivo CSV: {str(e)}"

    # Verificar se o CSV está vazio
    if data.empty:
        return False, "O arquivo CSV está vazio."

    # Verificar número de colunas
    if len(data.columns) != len(fields):
        return False, f"O número de colunas no arquivo CSV ({len(data.columns)}) não corresponde ao esperado ({len(fields)})."

    # Verificar nomes das colunas
    expected_columns = [field["name"] for field in fields]
    if list(data.columns) != expected_columns:
        return False, f"As colunas do arquivo CSV não correspondem às esperadas. Esperado: {expected_columns}, recebido: {list(data.columns)}."

    # Validar tipos de dados e obrigatoriedade
    for field in fields:
        column_name = field["name"]
        column_type = field["type"]
        is_required = field["required"]

        # Verificar valores ausentes em colunas obrigatórias
        if is_required and data[column_name].isnull().any():
            return False, f"A coluna '{column_name}' contém valores ausentes, mas é obrigatória."

        # Verificar tipos de dados
        if column_type == "INT" and not pd.api.types.is_integer_dtype(data[column_name].dropna()):
            return False, f"A coluna '{column_name}' deve conter apenas números inteiros."
        if column_type == "FLOAT" and not pd.api.types.is_float_dtype(data[column_name].dropna()):
            return False, f"A coluna '{column_name}' deve conter apenas números decimais."
        if column_type == "VARCHAR" and not pd.api.types.is_string_dtype(data[column_name].dropna()):
            return False, f"A coluna '{column_name}' deve conter apenas texto."
        if column_type == "BOOLEAN" and not data[column_name].dropna().isin([True, False, "true", "false", 1, 0]).all():
            return False, f"A coluna '{column_name}' deve conter apenas valores booleanos (True/False)."
        if column_type == "DATE":
            try:
                pd.to_datetime(data[column_name].dropna(), format="%Y-%m-%d", errors="raise")
            except ValueError:
                return False, f"A coluna '{column_name}' deve conter datas no formato 'YYYY-MM-DD'."

    # Se todas as validações passarem
    return True, "Arquivo CSV validado com sucesso."

# Rota para obter e salvar a configuração das colunas
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

# Rota para listar os dados salvos no banco de dados
@app.route("/api/data", methods=["GET"])
def list_form_data():
    try:
        # Conectar ao banco de dados
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM form_responses")
            rows = cursor.fetchall()

            # Substituir valores NaN por null
            data = [{"id": row[0], "data": json.loads(row[1])} for row in rows]

        return jsonify(data), 200
    except Exception as e:
        print(f"Erro ao listar dados: {str(e)}")
        return jsonify({"error": f"Erro ao listar dados: {str(e)}"}), 500

# Rota para salvar novos dados do formulário
@app.route("/api/data", methods=["POST"])
def save_form_data():
    try:
        data = request.json

        # Substituir valores vazios ou inválidos por None
        data = {key: (value if value != "" else None) for key, value in data.items()}

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO form_responses (data) VALUES (?)", [json.dumps(data)])
            conn.commit()
        return jsonify({"message": "Dados salvos com sucesso!"})
    except Exception as e:
        print(f"Erro ao salvar dados do formulário: {str(e)}")
        return jsonify({"error": f"Erro ao salvar dados do formulário: {str(e)}"}), 500

# Rota para editar dados existentes
@app.route("/api/data/<int:data_id>", methods=["PUT"])
def edit_form_data(data_id):
    try:
        new_data = request.json
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Verificar se o ID existe
            cursor.execute("SELECT * FROM form_responses WHERE id = ?", (data_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Registro não encontrado."}), 404

            cursor.execute(
                "UPDATE form_responses SET data = ? WHERE id = ?", 
                [json.dumps(new_data), data_id]
            )
            conn.commit()
        return jsonify({"message": "Dados atualizados com sucesso!"})
    except Exception as e:
        print(f"Erro ao editar dados: {str(e)}")
        return jsonify({"error": f"Erro ao editar dados: {str(e)}"}), 500

# Rota para excluir dados
@app.route("/api/data/<int:data_id>", methods=["DELETE"])
def delete_form_data(data_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Verificar se o ID existe
            cursor.execute("SELECT * FROM form_responses WHERE id = ?", (data_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Registro não encontrado."}), 404

            cursor.execute("DELETE FROM form_responses WHERE id = ?", (data_id,))
            conn.commit()
        return jsonify({"message": "Dados excluídos com sucesso!"})
    except Exception as e:
        print(f"Erro ao excluir dados: {str(e)}")
        return jsonify({"error": f"Erro ao excluir dados: {str(e)}"}), 500

# Rota para upload de arquivos CSV
@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Apenas arquivos .csv são suportados"}), 400

    # Salvar o arquivo CSV no diretório de uploads
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # Validar o arquivo CSV
    is_valid, message = validate_csv(file_path)
    if not is_valid:
        os.remove(file_path)  # Remover o arquivo inválido
        return jsonify({"error": message}), 400

    try:
        # Processar o arquivo CSV (após validação bem-sucedida)
        data = pd.read_csv(file_path, encoding="utf-8")

        # Substituir NaN por None para compatibilidade com JSON
        data = data.replace({np.nan: None})
        data_records = data.to_dict(orient="records")

        # Salvar cada linha no banco de dados
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for record in data_records:
                cursor.execute("INSERT INTO form_responses (data) VALUES (?)", [json.dumps(record)])
            conn.commit()

        os.remove(file_path)  # Remover o arquivo após o processamento
        return jsonify({"message": "Arquivo CSV carregado com sucesso!", "data": data_records})
    except Exception as e:
        os.remove(file_path)  # Remover o arquivo em caso de erro
        print(f"Erro ao processar o arquivo CSV: {str(e)}")
        return jsonify({"error": f"Erro ao processar o arquivo: {str(e)}"}), 500

# Inicializa o banco de dados ao iniciar o app
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
