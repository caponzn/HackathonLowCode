from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import json

app = Flask(__name__)
CORS(app)  # Habilitar CORS para permitir requisições de diferentes origens

# Diretórios e arquivos de configuração
UPLOAD_FOLDER = "uploads"
CONFIG_FILE = "form_config.json"
DATA_FILE = "form_data.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Funções auxiliares para lidar com arquivos JSON
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
@app.route("/api/config", methods=["GET"])
def get_form_config():
    config = load_json(CONFIG_FILE, {"fields": []})
    return jsonify(config)

# Rota para salvar a configuração das colunas
@app.route("/api/config", methods=["POST"])
def save_form_config():
    config = request.json
    save_json(CONFIG_FILE, config)
    return jsonify({"message": "Configuração salva com sucesso!"})

# Rota para listar os dados salvos
@app.route("/api/data", methods=["GET"])
def list_form_data():
    data = load_json(DATA_FILE, [])
    return jsonify(data)

# Rota para salvar dados do formulário com validação
@app.route("/api/data", methods=["POST"])
def save_form_data():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Nenhum dado enviado"}), 400

        config = load_json(CONFIG_FILE, {"fields": []})
        fields = config.get("fields", [])

        errors = []
        # Validar os dados recebidos com base na configuração
        for field in fields:
            name = field["name"]
            value = data.get(name)
            required = field.get("required", False)
            max_length = field.get("maxLength")
            min_value = field.get("min")
            max_value = field.get("max")
            field_type = field.get("type")

            # Verificar se o campo é obrigatório
            if required and (value is None or value == ""):
                errors.append(f"O campo '{name}' é obrigatório.")
                continue

            # Converter valores para o tipo correto
            if value is not None:
                try:
                    if field_type == "INT":
                        value = int(value)  # Converter para inteiro
                    elif field_type == "FLOAT":
                        value = float(value)  # Converter para número real
                except ValueError:
                    errors.append(f"O campo '{name}' deve ser um número válido.")
                    continue

                # Verificar tamanho máximo (para strings)
                if field_type == "VARCHAR" and max_length and isinstance(value, str) and len(value) > max_length:
                    errors.append(f"O campo '{name}' excede o tamanho máximo de {max_length} caracteres.")
                    continue

                # Verificar limites numéricos
                if field_type in ["INT", "FLOAT"]:
                    if min_value is not None and value < min_value:
                        errors.append(f"O campo '{name}' deve ser maior ou igual a {min_value}.")
                    if max_value is not None and value > max_value:
                        errors.append(f"O campo '{name}' deve ser menor ou igual a {max_value}.")

        if errors:
            return jsonify({"errors": errors}), 400

        # Salvar os dados se não houver erros
        existing_data = load_json(DATA_FILE, [])
        existing_data.append(data)
        save_json(DATA_FILE, existing_data)

        return jsonify({"message": "Dados salvos com sucesso!"})
    except Exception as e:
        print(f"Erro interno: {e}")  # Log do erro para depuração
        return jsonify({"error": "Erro interno no servidor"}), 500

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
        # Ler os dados do CSV
        data = pd.read_csv(file_path)
        # Validar os dados com base na configuração
        config = load_json(CONFIG_FILE, {"fields": []})
        fields = config.get("fields", [])
        errors = []

        # Validar cada linha
        for index, row in data.iterrows():
            for field in fields:
                name = field["name"]
                if name not in row:
                    errors.append(f"A coluna '{name}' está faltando no arquivo.")
                    continue

                value = row[name]
                required = field.get("required", False)
                max_length = field.get("maxLength")
                min_value = field.get("min")
                max_value = field.get("max")
                field_type = field.get("type")

                # Verificar obrigatoriedade
                if required and pd.isna(value):
                    errors.append(f"O campo '{name}' na linha {index + 1} é obrigatório.")
                    continue

                # Verificar tamanho máximo
                if field_type == "VARCHAR" and max_length and isinstance(value, str) and len(value) > max_length:
                    errors.append(f"O campo '{name}' na linha {index + 1} excede o tamanho máximo de {max_length}.")
                    continue

                # Verificar limites numéricos
                if field_type in ["INT", "FLOAT"]:
                    try:
                        value = float(value) if field_type == "FLOAT" else int(value)
                        if min_value is not None and value < min_value:
                            errors.append(f"O campo '{name}' na linha {index + 1} deve ser maior ou igual a {min_value}.")
                        if max_value is not None and value > max_value:
                            errors.append(f"O campo '{name}' na linha {index + 1} deve ser menor ou igual a {max_value}.")
                    except ValueError:
                        errors.append(f"O campo '{name}' na linha {index + 1} deve ser um número válido.")

        if errors:
            return jsonify({"errors": errors}), 400

        # Salvar os dados do CSV no arquivo de dados
        existing_data = load_json(DATA_FILE, [])
        existing_data.extend(data.to_dict(orient="records"))
        save_json(DATA_FILE, existing_data)

        return jsonify({"message": "Arquivo carregado e validado com sucesso!"})
    except Exception as e:
        print(f"Erro interno: {e}")  # Log do erro para depuração
        return jsonify({"error": f"Erro ao processar o arquivo: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
