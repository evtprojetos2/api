import json
from flask import Flask, jsonify, request, redirect, Response
from unidecode import unidecode
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature 
import time
from urllib.parse import unquote 
import requests 

# --- Variáveis Globais de Segurança e Configuração ---

app = Flask(__name__) 

# TEMPO DE EXPIRAÇÃO DO LINK: 4 horas = 4 * 3600 = 14400 segundos
TEMPO_EXPIRACAO_LINK = 14400 

# CHAVE SECRETA para assinar/validar links temporários. Mude este valor!
SECRET_KEY_ASSINATURA = "sua_chave_secreta_para_assinatura_de_links_XYZ"

signer = URLSafeTimedSerializer(SECRET_KEY_ASSINATURA, salt='media-access-salt')

# Defina o caractere que separa os gêneros no seu 'filmes_capturados.json'
SPLIT_CHAR = ',' 
# ------------------------------------------------------------------------

# Nomes dos arquivos de dados
DATA_FILE = 'filmes_capturados.json'
TOKENS_FILE = 'api_tokens.json'

# --- Funções Auxiliares de Dados e Autenticação ---

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
    Remove chaves sensíveis/internas, LIMPA AS URLS, e 
    converte o valor da chave 'generos' para MAIÚSCULO.
    """
    EXCLUDE_KEYS = ['url_player_pagina', 'url_filme', 'url_m3u8_ou_mp4']
    URL_KEYS_TO_CLEAN = ['url_capa', 'url_poster'] 
    
    filtered_movie = movie.copy()
    
    # 1. Remove chaves sensíveis
    for key in EXCLUDE_KEYS:
        filtered_movie.pop(key, None)
        
    # 2. Limpa as aspas simples extras das URLs
    for key in URL_KEYS_TO_CLEAN:
        if key in filtered_movie and isinstance(filtered_movie[key], str):
            # O método .strip("'") remove a aspa simples no início e no fim da string
            filtered_movie[key] = filtered_movie[key].strip("'")
            
    # 3. [MODIFICAÇÃO SOLICITADA] Garante que o valor de 'generos' venha em MAIÚSCULO
    if 'generos' in filtered_movie and isinstance(filtered_movie['generos'], str):
        filtered_movie['generos'] = filtered_movie['generos'].upper()
            
    return filtered_movie

# Carregamento global na inicialização
FILMES, CATEGORIAS_COMPLETAS = load_data()
VALID_TOKENS = load_tokens()

CATEGORIAS_NORM = {
    unidecode(cat).lower(): cat
    for cat in CATEGORIAS_COMPLETAS
}

def require_api_token(f):
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

# --- ROTAS DE LISTAGEM E BUSCA (ARRAY JSON) ---

@app.route('/', methods=['GET'])
@require_api_token
def get_all_content():
    """Lista todos os filmes com ID e dados filtrados (retorna um array direto)."""
    filmes_com_id = []
    for i, filme in enumerate(FILMES):
        filme_filtrado = filter_movie_data(filme)
        filme_filtrado['filme_id'] = i
        filmes_com_id.append(filme_filtrado)
        
    return jsonify(filmes_com_id)

@app.route('/categorias', methods=['GET'])
@require_api_token
def get_all_categories():
    """
    Lista todas as categorias, retornando um Array JSON de objetos no formato [{"cat": "nome_categoria"}].
    """
    # MODIFICAÇÃO: Converte a lista simples em uma lista de objetos {"cat": ...}
    categorias_formatadas = [{"cat": c} for c in CATEGORIAS_COMPLETAS]
    
    return jsonify(categorias_formatadas)
    
@app.route('/<string:categoria_ou_genero>', methods=['GET'])
@require_api_token
def get_content_by_category(categoria_ou_genero):
    """Filtra por gênero (retorna um array direto)."""
    termo_normalizado = unidecode(categoria_ou_genero).strip().lower()
    resultados = []
    
    for i, filme in enumerate(FILMES):
        generos_filme = filme.get('generos', '')
        generos_norm_filme = [unidecode(g).strip().lower() for g in generos_filme.split(SPLIT_CHAR)]
        
        if termo_normalizado in generos_norm_filme:
            filme_filtrado = filter_movie_data(filme)
            filme_filtrado['filme_id'] = i
            resultados.append(filme_filtrado)

    if not resultados:
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para: {categoria_ou_genero}",
            "filmes": []
        }), 404
        
    return jsonify(resultados)


@app.route('/titulo/<string:titulo_busca>', methods=['GET'])
@require_api_token
def get_content_by_title(titulo_busca):
    """Busca por título (retorna um array direto)."""
    titulo_busca_decoded = unquote(titulo_busca)
    termo_busca_normalizado = unidecode(titulo_busca_decoded).strip().lower().replace('+', ' ')
    
    resultados = []
    for i, filme in enumerate(FILMES):
        titulo_filme_normalizado = unidecode(filme.get('titulo', '')).strip().lower()

        if termo_busca_normalizado in titulo_filme_normalizado:
            filme_filtrado = filter_movie_data(filme)
            filme_filtrado['filme_id'] = i 
            
            resultados.append(filme_filtrado)

    if not resultados:
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para o título: {titulo_busca}",
            "filmes": []
        }), 404
        
    return jsonify(resultados)


@app.route('/ano/<string:ano_busca>', methods=['GET'])
@require_api_token
def get_content_by_year(ano_busca):
    """Busca por ano (retorna um array direto)."""
    ano_normalizado = ano_busca.strip()
    resultados = []
    
    for i, filme in enumerate(FILMES):
        if filme.get('ano', '').strip() == ano_normalizado:
            filme_filtrado = filter_movie_data(filme)
            filme_filtrado['filme_id'] = i
            resultados.append(filme_filtrado)

    if not resultados:
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para o ano: {ano_busca}",
            "filmes": []
        }), 404
        
    return jsonify(resultados)

# --- ROTA DE PLAYER (RETORNA ARRAY JSON) ---

@app.route('/titulo/<string:titulo_busca>/player', methods=['GET'])
@require_api_token
def generate_player_link_by_title(titulo_busca):
    """Gera o link temporário de 4 horas (URL completa), retornando um ARRAY JSON."""
    titulo_busca_decoded = unquote(titulo_busca)
    termo_busca_normalizado = unidecode(titulo_busca_decoded).strip().lower().replace('+', ' ')
    
    filme_encontrado = None
    filme_id = -1
    
    for i, filme in enumerate(FILMES):
        titulo_filme_normalizado = unidecode(filme.get('titulo', '')).strip().lower()
        if termo_busca_normalizado in titulo_filme_normalizado:
            filme_encontrado = filme
            filme_id = i
            break

    if not filme_encontrado:
        return jsonify({"erro": f"Filme com título '{titulo_busca}' não encontrado."}), 404

    url_sensivel = filme_encontrado.get('url_m3u8_ou_mp4')
    if not url_sensivel or url_sensivel == 'N/A':
        return jsonify({"erro": f"Filme '{filme_encontrado['titulo']}' não possui URL de mídia (url_m3u8_ou_mp4)."}), 500

    payload = url_sensivel
    temp_token = signer.dumps(payload)
    
    base_url = request.url_root.rstrip('/')
    link_temporario = f"{base_url}/player_proxy/{filme_id}?temp_token={temp_token}"
    
    # Resposta encapsulada em uma lista []
    resposta_player = [{
        "status": "sucesso",
        "filme": filme_encontrado['titulo'],
        "link_temporario": link_temporario, 
        "expira_em_segundos": TEMPO_EXPIRACAO_LINK
    }]
    
    return jsonify(resposta_player) 
    
# --- ROTA DE PROXY (MANTIDA) ---

@app.route('/player_proxy/<int:filme_id>', methods=['GET'])
def player_proxy(filme_id):
    """Valida o token e serve o stream de mídia (máscara de URL)."""
    temp_token = request.args.get('temp_token')
    if not temp_token:
        return jsonify({"erro": "Acesso negado. Token temporário ausente."}), 401
        
    try:
        url_original = signer.loads(temp_token, max_age=TEMPO_EXPIRACAO_LINK)

        try:
             filme_real = FILMES[filme_id]
             if url_original != filme_real.get('url_m3u8_ou_mp4'):
                 return jsonify({"erro": "Token válido, mas ID do filme incorreto ou URL de mídia alterada."}), 401
        except IndexError:
             return jsonify({"erro": "ID de filme no proxy inválido."}), 404
             
        headers = {key: value for (key, value) in request.headers if key != 'Host'}
        
        resp = requests.request(
            method=request.method,
            url=url_original,
            headers=headers,
            data=request.get_data(),
            stream=True, 
            allow_redirects=False
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                            if name.lower() not in excluded_headers]
                            
        return Response(
            resp.iter_content(chunk_size=1024), 
            status=resp.status_code,
            headers=response_headers,
            content_type=resp.headers.get('Content-Type')
        )

    except SignatureExpired:
        return jsonify({"erro": "Acesso negado. O link expirou (4 horas)."}), 401
    except BadTimeSignature:
        return jsonify({"erro": "Acesso negado. O token é inválido ou foi adulterado."}), 401
    except requests.exceptions.RequestException as e:
         return jsonify({"erro": f"Erro ao conectar com a fonte de mídia: {str(e)}"}), 503
    except Exception as e:
        return jsonify({"erro": f"Erro interno ao validar o link: {str(e)}"}), 500

# --- ROTA DE DOCUMENTAÇÃO ---

DOCUMENTATION_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Docs | API de Mídia</title>
    <style>
        body { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif; margin: 0; padding: 0; background-color: #f7f9fc; color: #333; }
        .header { background-color: #007bff; color: white; padding: 20px 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
        .header h1 { margin: 0; font-size: 2em; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .section { background-color: white; border: 1px solid #e0e6ed; border-radius: 8px; margin-bottom: 20px; padding: 20px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05); }
        .section h2 { border-bottom: 2px solid #007bff; padding-bottom: 10px; margin-top: 0; color: #007bff; }
        
        /* Model Schema Styling */
        .schema-container h3 { color: #343a40; margin-top: 15px; border-bottom: 1px dotted #ccc; padding-bottom: 5px; }
        .schema pre { background-color: #f0f3f6; padding: 15px; border-radius: 6px; overflow-x: auto; font-size: 0.9em; border-left: 5px solid #007bff; }
        
        /* Endpoints Table */
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e0e6ed; font-size: 0.95em; }
        th { background-color: #e9ecef; color: #495057; font-weight: 600; }
        .method { font-weight: bold; padding: 4px 8px; border-radius: 4px; color: white; margin-right: 10px; font-size: 0.8em; }
        .get { background-color: #28a745; } /* Green */
        .post { background-color: #007bff; } /* Blue */
        .path { font-family: monospace; background-color: #f0f3f6; padding: 2px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 API de Mídia</h1>
        <p>Documentação da API REST para Filmes e Conteúdo. Versão 1.0</p>
    </div>
    <div class="container">

        <div class="section">
            <h2>🔑 Autenticação</h2>
            <p>Todas as rotas de conteúdo exigem um **Token de Acesso à API** válido.</p>
            
            <h3>Métodos de Envio do Token:</h3>
            <ul>
                <li><strong>Preferencial (Header):</strong> <code>Authorization: Bearer SEU_TOKEN_AQUI</code></li>
                <li><strong>Alternativa (Query):</strong> Adicione <code>?token=SEU_TOKEN_AQUI</code> ao final da URL.</li>
            </ul>
        </div>

        <div class="section schema-container">
            <h2>📐 Modelos (Schemas JSON)</h2>

            <h3>Filme (Objeto Principal)</h3>
            <div class="schema">
<pre>
[
  {
    "ano": "string",
    "classificacao": "string",
    "duracao": "string",
    "filme_id": "integer",
    "generos": "string (separados por vírgula) - SEMPRE EM MAIÚSCULO",
    "imdb": "string (IMDbX.X)",
    "sinopse": "string",
    "titulo": "string",
    "url_capa": "string (URL limpa)",
    "url_poster": "string (URL limpa)",
    "views": "string (Ex: 8,990)"
  },
  ...
]
</pre>
            </div>
            
            <h3>Categorias (Array de Objetos)</h3>
            <div class="schema">
<pre>
[ 
  {"cat": "netflix"}, 
  {"cat": "discovery"}, 
  {"cat": "4k"}, 
  // ...
]
</pre>
            </div>
            
            <h3>Resposta de Player (Array Consistente)</h3>
            <div class="schema">
<pre>
[
  {
    "status": "sucesso",
    "filme": "string (Título)",
    "link_temporario": "string (URL completa do Proxy)",
    "expira_em_segundos": "integer"
  }
]
</pre>
            </div>
            
             <h3>Erro (Resposta Padrão)</h3>
            <div class="schema">
<pre>
{
  "erro": "string",
  "mensagem": "string (opcional)",
  "filmes": [] (em caso de 404, para manter o tipo array)
}
</pre>
            </div>
        </div>

        <div class="section">
            <h2>🗺️ Endpoints de Listagem e Busca</h2>
            <p>Em caso de sucesso (200 OK), estas rotas retornam um <strong>Array JSON</strong> (<code>[...]</code>) de objetos Filme.</p>

            <table>
                <thead>
                    <tr>
                        <th>Método</th>
                        <th>Caminho</th>
                        <th>Descrição</th>
                        <th>Parâmetro</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/</span></td>
                        <td>Lista todos os filmes disponíveis na base de dados.</td>
                        <td>Nenhum</td>
                    </tr>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/categorias</span></td>
                        <td>Lista todas as categorias/gêneros (Retorna Array de Objetos <code>[{"cat": ...}]</code>).</td>
                        <td>Nenhum</td>
                    </tr>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/{genero}</span></td>
                        <td>Filtra filmes por Categoria/Gênero. Ex: <code>/Terror</code></td>
                        <td>Gênero (string)</td>
                    </tr>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/titulo/{titulo_busca}</span></td>
                        <td>Busca filmes por título (parcial ou completo).</td>
                        <td>Título (string)</td>
                    </tr>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/ano/{ano_busca}</span></td>
                        <td>Filtra filmes por ano de lançamento. Ex: <code>/ano/2025</code></td>
                        <td>Ano (string)</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📺 Endpoints de Mídia (Proxy Seguro)</h2>
            <p>Este fluxo utiliza um token temporário (expira em 4 horas) para proteger a URL de streaming original.</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Método</th>
                        <th>Caminho</th>
                        <th>Descrição</th>
                        <th>Retorno</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/titulo/{titulo}/player</span></td>
                        <td><strong>Gera o link temporário de streaming (Retorna Array JSON).</strong></td>
                        <td>Array JSON (<code>[{...}]</code>)</td>
                    </tr>
                    <tr>
                        <td><span class="method get">GET</span></td>
                        <td><span class="path">/player_proxy/{filme_id}</span></td>
                        <td><strong>Proxy de Mídia.</strong> Endpoint final acessado pelo player, que valida o <code>temp_token</code>.</td>
                        <td>Fluxo de Mídia (MP4/M3U8)</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/docs', methods=['GET'])
def api_documentation():
    """Rota para servir a documentação em HTML."""
    return Response(DOCUMENTATION_HTML, mimetype='text/html')

# Rotas base para compatibilidade
@app.route('/', methods=['GET'])
@require_api_token
def get_all_content_base():
    return get_all_content()

@app.route('/categorias', methods=['GET'])
@require_api_token
def get_all_categories_base():
    return get_all_categories()
