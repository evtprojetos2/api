import json
from flask import Flask, jsonify
from unidecode import unidecode 

# --- Configuração do Flask e Carregamento de Dados ---

# A variável 'app' é o ponto de entrada que o Vercel procura
app = Flask(__name__) 

# Nome do arquivo de dados
DATA_FILE = 'filmes_capturados.json'

def load_data():
    """Carrega os dados do arquivo JSON."""
    try:
        # Abre o arquivo de dados
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['filmes'], data['categorias_capturadas']
    except Exception as e:
        print(f"Erro ao carregar dados: {e}")
        return [], []

FILMES, CATEGORIAS_COMPLETAS = load_data()

# Pré-processa as categorias para buscas mais robustas (sem acento, minúsculas)
CATEGORIAS_NORM = {
    unidecode(cat).lower(): cat
    for cat in CATEGORIAS_COMPLETAS
}

# --- Rotas da API ---

@app.route('/', methods=['GET'])
def get_all_content():
    """Rota raiz: Retorna todos os filmes."""
    return jsonify({
        "total_filmes": len(FILMES),
        "filmes": FILMES
    })

@app.route('/categorias', methods=['GET'])
def get_all_categories():
    """Retorna a lista de todas as categorias e gêneros disponíveis."""
    return jsonify({
        "total_categorias": len(CATEGORIAS_COMPLETAS),
        "categorias": CATEGORIAS_COMPLETAS
    })

@app.route('/<string:categoria_ou_genero>', methods=['GET'])
def get_content_by_category(categoria_ou_genero):
    """Filtra e retorna o conteúdo baseado na categoria ou gênero fornecido."""
    
    # Normaliza o termo de busca
    termo_normalizado = unidecode(categoria_ou_genero).strip().lower()

    resultados = []
    for filme in FILMES:
        generos_filme = filme.get('generos', '')
        
        # Cria uma lista de gêneros normalizados para o filme
        generos_norm_filme = [
            unidecode(g).strip().lower() 
            for g in generos_filme.split(',')
        ]
        
        # Verifica a correspondência
        if termo_normalizado in generos_norm_filme:
            resultados.append(filme)

    if not resultados:
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para: {categoria_ou_genero}",
            "filmes": []
        }), 404
        
    return jsonify({
        "categoria_pesquisada": categoria_ou_genero,
        "total_encontrado": len(resultados),
        "filmes": resultados
    })
