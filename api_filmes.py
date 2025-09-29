import json
from flask import Flask, jsonify, request
from unidecode import unidecode
from functools import wraps

# --- Configuração do Flask e Carregamento de Dados ---

app = Flask(__name__) 

# Defina o caractere que separa os gêneros no seu 'filmes_capturados.json'
SPLIT_CHAR = ',' # ATUALIZE para ';' ou '|' se for o caso
# ------------------------------------------------------------------------

# Nomes dos arquivos de dados
DATA_FILE = 'filmes_capturados.json'
TOKENS_FILE = 'api_tokens.json'


# --- Funções de Carregamento ---

def load_data():
    """Carrega os dados dos filmes e categorias."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['filmes'], data['categorias_capturadas']
    except Exception as e:
        print(f"ERRO: Falha ao carregar {DATA_FILE}: {e}")
        return [], []

def load_tokens():
    """Carrega os tokens válidos do arquivo JSON."""
    try:
        with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Usa 'set' para buscas de token ultra-rápidas (O(1))
        return set(data.get('valid_tokens', [])) 
    except FileNotFoundError:
        print(f"AVISO: Arquivo '{TOKENS_FILE}' não encontrado. A API estará bloqueada.")
        return set()
    except json.JSONDecodeError:
        print(f"ERRO: Não foi possível decodificar o JSON do arquivo '{TOKENS_FILE}'.")
        return set()

# Carregamento global na inicialização
FILMES, CATEGORIAS_COMPLETAS = load_data()
VALID_TOKENS = load_tokens()

CATEGORIAS_NORM = {
    unidecode(cat).lower(): cat
    for cat in CATEGORIAS_COMPLETAS
}

# --- Decorador de Autenticação ---

def require_api_token(f):
    """Verifica se um token fornecido está na lista VALID_TOKENS carregada."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Tenta obter o token do cabeçalho 'Authorization' (Bearer)
        auth_header = request.headers.get('Authorization')
        token = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Tenta obter o token do parâmetro de consulta (?token=...)
        if not token:
            token = request.args.get('token')
            
        # Verifica se o token está no SET de tokens válidos
        if token and token in VALID_TOKENS:
            return f(*args, **kwargs)
        else:
            return jsonify({"erro": "Acesso negado. Token de API inválido ou ausente."}), 401 # 401 Unauthorized
            
    return decorated

# --- Rotas da API (PROTEGIDAS) ---

@app.route('/', methods=['GET'])
@require_api_token
def get_all_content():
    return jsonify({
        "total_filmes": len(FILMES),
        "filmes": FILMES
    })

@app.route('/categorias', methods=['GET'])
@require_api_token
def get_all_categories():
    return jsonify({
        "total_categorias": len(CATEGORIAS_COMPLETAS),
        "categorias": CATEGORIAS_COMPLETAS
    })

@app.route('/<string:categoria_ou_genero>', methods=['GET'])
@require_api_token
def get_content_by_category(categoria_ou_genero):
    
    termo_normalizado = unidecode(categoria_ou_genero).strip().lower()

    resultados = []
    for filme in FILMES:
        generos_filme = filme.get('generos', '')
        
        generos_norm_filme = [
            unidecode(g).strip().lower() 
            for g in generos_filme.split(SPLIT_CHAR) # Usa o separador definido
        ]
        
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
