from flask import Flask, request, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)  # Para permitir comunicação com o frontend

# Armazena configurações de formulário e dados temporários
config_file = "form_config.json"
data_file = "form_data.json"

# Carregar ou inicializar arquivos
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        with open(file, "w") as f:
            json.dump(default, f)
        return default

# Salvar dados em arquivo
def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Rota para configurar o formulário
@app.route("/api/config", methods=["POST"])
def set_form_config():
    config = request.json
    save_json(config_file, config)
    return jsonify({"message": "Configuração salva com sucesso!"})

# Rota para obter configuração do formulário
@app.route("/api/config", methods=["GET"])
def get_form_config():
    config = load_json(config_file, {"fields": []})
    return jsonify(config)

# Rota para salvar dados do formulário
@app.route("/api/data", methods=["POST"])
def save_form_data():
    data = request.json
    existing_data = load_json(data_file, [])
    existing_data.append(data)
    save_json(data_file, existing_data)
    return jsonify({"message": "Dados salvos com sucesso!"})

# Rota para listar dados salvos
@app.route("/api/data", methods=["GET"])
def list_form_data():
    data = load_json(data_file, [])
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
