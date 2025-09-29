import json
from flask import Flask, jsonify, request, redirect
from unidecode import unidecode
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature 
import time

# --- Variáveis Globais de Segurança e Configuração ---

app = Flask(__name__) 

# 1. TEMPO DE EXPIRAÇÃO DO LINK: 4 horas = 4 * 3600 = 14400 segundos
TEMPO_EXPIRACAO_LINK = 14400 

# CHAVE SECRETA para assinar/validar links temporários. 
# EM PRODUÇÃO, use Variáveis de Ambiente do Vercel!
SECRET_KEY_ASSINATURA = "sua_chave_secreta_para_assinatura_de_links_XYZ"

# Inicializa o serializador
signer = URLSafeTimedSerializer(SECRET_KEY_ASSINATURA, salt='media-access-salt')

# Defina o caractere que separa os gêneros no seu 'filmes_capturados.json'
SPLIT_CHAR = ',' # ATUALIZE para ';' ou '|' se for o caso
# ------------------------------------------------------------------------

# Nomes dos arquivos de dados
DATA_FILE = 'filmes_capturados.json'
TOKENS_FILE = 'api_tokens.json'

# --- Funções Auxiliares ---

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
    """Carrega os tokens válidos do arquivo JSON (tokens de acesso à API)."""
    try:
        with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return set(data.get('valid_tokens', [])) 
    except Exception:
        return set()

def filter_movie_data(movie: dict) -> dict:
    """
    Remove chaves sensíveis/internas do objeto do filme antes de retornar na rota de detalhes.
    Estas chaves só devem ser acessíveis via link temporário.
    """
    # Chaves a serem removidas da resposta pública
    EXCLUDE_KEYS = ['url_player_pagina', 'url_filme', 'url_m3u8_ou_mp4']
    
    filtered_movie = movie.copy()
    for key in EXCLUDE_KEYS:
        filtered_movie.pop(key, None)
    return filtered_movie

# Carregamento global na inicialização
FILMES, CATEGORIAS_COMPLETAS = load_data()
VALID_TOKENS = load_tokens()

CATEGORIAS_NORM = {
    unidecode(cat).lower(): cat
    for cat in CATEGORIAS_COMPLETAS
}

# --- Decorador de Autenticação ---

def require_api_token(f):
    """Verifica se um token de acesso à API está na lista de tokens válidos."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1] if auth_header and auth_header.startswith('Bearer ') else None
        if not token:
            token = request.args.get('token')
            
        if token and token in VALID_TOKENS:
            return f(*args, **kwargs)
        else:
            return jsonify({"erro": "Acesso negado. Token de API inválido ou ausente."}), 401
            
    return decorated

# --- ROTAS DE BUSCA POR TÍTULO (Detalhamento) ---

@app.route('/titulo/<string:titulo_busca>', methods=['GET'])
@require_api_token
def get_content_by_title(titulo_busca):
    """
    Busca e retorna detalhes do conteúdo pelo título, REMOVENDO os links de mídia.
    """
    termo_busca_normalizado = unidecode(titulo_busca).strip().lower().replace('+', ' ')
    
    resultados = []
    for i, filme in enumerate(FILMES):
        titulo_filme_normalizado = unidecode(filme.get('titulo', '')).strip().lower()

        if termo_busca_normalizado in titulo_filme_normalizado:
            # 1. Filtra as chaves sensíveis (url_m3u8_ou_mp4, url_filme, url_player_pagina)
            filme_filtrado = filter_movie_data(filme)
            
            # 2. Adiciona o ID (para que o cliente possa chamar a rota /player)
            filme_filtrado['filme_id'] = i 
            
            resultados.append(filme_filtrado)

    if not resultados:
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para o título: {titulo_busca}",
            "filmes": []
        }), 404
        
    return jsonify({
        "titulo_pesquisado": titulo_busca,
        "total_encontrado": len(resultados),
        "filmes": resultados
    })

# --- ROTA DE PLAYER POR TÍTULO (Geração do Token Temporário) ---

@app.route('/titulo/<string:titulo_busca>/player', methods=['GET'])
@require_api_token
def generate_player_link_by_title(titulo_busca):
    """
    Busca o filme pelo título e gera o link temporário para o player.
    O token tem validade de 4 horas.
    """
    termo_busca_normalizado = unidecode(titulo_busca).strip().lower().replace('+', ' ')
    
    filme_encontrado = None
    filme_id = -1
    
    # Localiza o filme
    for i, filme in enumerate(FILMES):
        titulo_filme_normalizado = unidecode(filme.get('titulo', '')).strip().lower()
        if termo_busca_normalizado in titulo_filme_normalizado:
            filme_encontrado = filme
            filme_id = i
            break

    if not filme_encontrado:
        return jsonify({"erro": f"Filme com título '{titulo_busca}' não encontrado."}), 404

    # Pega o link sensível que queremos proteger (o único que aparece agora)
    url_sensivel = filme_encontrado.get('url_m3u8_ou_mp4')
    if not url_sensivel:
        return jsonify({"erro": f"Filme '{filme_encontrado['titulo']}' não possui URL de mídia (url_m3u8_ou_mp4)."}), 500

    # Gera o token temporário (4 horas de validade implícita)
    payload = url_sensivel
    temp_token = signer.dumps(payload)
    
    # Constrói o link temporário que aponta para o seu proxy
    link_temporario = f"/player_proxy/{filme_id}?temp_token={temp_token}"
    
    return jsonify({
        "status": "sucesso",
        "filme": filme_encontrado['titulo'],
        "link_temporario": link_temporario, 
        "expira_em_segundos": TEMPO_EXPIRACAO_LINK
    })
    
# --- ROTA DE PROXY (Validação e Redirecionamento) ---

@app.route('/player_proxy/<int:filme_id>', methods=['GET'])
def player_proxy(filme_id):
    """
    Verifica o token temporário usando a expiração de 4 horas e redireciona.
    """
    temp_token = request.args.get('temp_token')
    if not temp_token:
        return jsonify({"erro": "Acesso negado. Token temporário ausente."}), 401
        
    try:
        # Tenta carregar (validar) o token. O max_age=14400s (4 horas) garante a expiração.
        url_original = signer.loads(temp_token, max_age=TEMPO_EXPIRACAO_LINK)

        # Verificação extra de segurança (se o ID corresponde ao token)
        try:
             filme_real = FILMES[filme_id]
             if url_original != filme_real.get('url_m3u8_ou_mp4'):
                 return jsonify({"erro": "Token válido, mas ID do filme incorreto."}), 401
        except IndexError:
             return jsonify({"erro": "ID de filme no proxy inválido."}), 404

        # Se for válido, redireciona o cliente (player) para a URL real
        return redirect(url_original, code=302)

    except SignatureExpired:
        return jsonify({"erro": "Acesso negado. O link expirou."}), 401
    except BadTimeSignature:
        return jsonify({"erro": "Acesso negado. O token é inválido ou foi adulterado."}), 401
    except Exception as e:
        return jsonify({"erro": f"Erro interno ao validar o link: {str(e)}"}), 500


# --- ROTAS DE LISTAGEM GERAL (MANTIDAS POR COMPLETO) ---
# ... (MANTENHA AQUI AS ROTAS / e /categorias)
