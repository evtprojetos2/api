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

# --- Funções Auxiliares ---

def load_data():
    """Carrega os dados dos filmes e categorias."""
    try:
        # Use a codificação correta se o seu JSON não for UTF-8 padrão
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
        # Cria um set vazio se o arquivo não existir ou for inválido
        return set()

def filter_movie_data(movie: dict) -> dict:
    """
    Remove chaves sensíveis/internas do objeto do filme antes de retornar na rota de detalhes.
    """
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

# --- ROTAS DE LISTAGEM E CATEGORIAS (SAÍDA LIMPA: ARRAY DIRETO) ---

@app.route('/', methods=['GET'])
@require_api_token
def get_all_content():
    """Lista todos os filmes com ID e dados filtrados (retorna um array direto)."""
    filmes_com_id = []
    for i, filme in enumerate(FILMES):
        filme_filtrado = filter_movie_data(filme)
        filme_filtrado['filme_id'] = i
        filmes_com_id.append(filme_filtrado)
        
    # Retorna o array de filmes diretamente
    return jsonify(filmes_com_id)

@app.route('/categorias', methods=['GET'])
@require_api_token
def get_all_categories():
    """Lista todas as categorias (mantém o objeto para contexto)."""
    return jsonify({
        "categorias": CATEGORIAS_COMPLETAS
    })
    
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
        # Erro continua encapsulado para clareza
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para: {categoria_ou_genero}",
            "filmes": []
        }), 404
        
    # Retorna o array de resultados diretamente
    return jsonify(resultados)


# --- ROTAS DE BUSCA POR TÍTULO E ANO (SAÍDA LIMPA: ARRAY DIRETO) ---

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
        # Erro continua encapsulado para clareza
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para o título: {titulo_busca}",
            "filmes": []
        }), 404
        
    # Retorna o array de resultados diretamente
    return jsonify(resultados)


@app.route('/ano/<string:ano_busca>', methods=['GET'])
@require_api_token
def get_content_by_year(ano_busca):
    """Busca por ano (retorna um array direto)."""
    ano_normalizado = ano_busca.strip()
    resultados = []
    
    for i, filme in enumerate(FILMES):
        # Compara o ano do filme com o ano da busca
        if filme.get('ano', '').strip() == ano_normalizado:
            filme_filtrado = filter_movie_data(filme)
            filme_filtrado['filme_id'] = i
            resultados.append(filme_filtrado)

    if not resultados:
        # Erro encapsulado para clareza
        return jsonify({
            "mensagem": f"Nenhum conteúdo encontrado para o ano: {ano_busca}",
            "filmes": []
        }), 404
        
    # Retorna o array de resultados diretamente
    return jsonify(resultados)

# --- ROTA DE PLAYER POR TÍTULO (MANTIDA) ---

@app.route('/titulo/<string:titulo_busca>/player', methods=['GET'])
@require_api_token
def generate_player_link_by_title(titulo_busca):
    """Gera o link temporário de 4 horas (URL completa)."""
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
    
    return jsonify({
        "status": "sucesso",
        "filme": filme_encontrado['titulo'],
        "link_temporario": link_temporario, 
        "expira_em_segundos": TEMPO_EXPIRACAO_LINK
    })
    
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
             # Garante que o ID do filme seja válido e a URL sensível corresponda
             filme_real = FILMES[filme_id]
             if url_original != filme_real.get('url_m3u8_ou_mp4'):
                 return jsonify({"erro": "Token válido, mas ID do filme incorreto ou URL de mídia alterada."}), 401
        except IndexError:
             return jsonify({"erro": "ID de filme no proxy inválido."}), 404
             
        headers = {key: value for (key, value) in request.headers if key != 'Host'}
        
        # Faz a requisição à URL de mídia real
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
        # Captura qualquer outro erro inesperado
        return jsonify({"erro": f"Erro interno ao validar o link: {str(e)}"}), 500

# --- NOVA ROTA DE DOCUMENTAÇÃO ---

# O bloco de HTML foi mantido dentro de uma string de aspas triplas para segurança.
DOCUMENTATION_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API de Mídia - Documentação</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f9; color: #333; }
        .container { max-width: 900px; margin: 0 auto; background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        h1 { color: #007bff; border-bottom: 3px solid #007bff; padding-bottom: 10px; margin-bottom: 20px; }
        h2 { color: #343a40; border-bottom: 1px solid #dee2e6; padding-bottom: 5px; margin-top: 30px; }
        pre, code { background-color: #e9ecef; padding: 2px 4px; border-radius: 4px; font-size: 0.9em; overflow-x: auto; }
        pre { padding: 10px; border: 1px solid #ced4da; }
        .method { font-weight: bold; padding: 2px 6px; border-radius: 4px; color: #fff; margin-right: 5px; }
        .get { background-color: #28a745; }
        .post { background-color: #007bff; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #dee2e6; }
        th { background-color: #f8f9fa; color: #495057; font-weight: 600; }
        .note { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 4px; border-left: 5px solid #ffc107; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 API de Mídia - Documentação</h1>
        <p>Bem-vindo à documentação oficial da API. Aqui você encontra todos os endpoints necessários para consumir os dados e o conteúdo de mídia.</p>
        
        <hr>

        <h2>🔑 Autenticação</h2>
        <p>Todas as rotas de busca e geração de link de player exigem um <strong>Token de Acesso à API</strong> válido (configurado em <code>api_tokens.json</code>).</p>
        
        <h3>Métodos de Envio do Token:</h3>
        <ol>
            <li><strong>Preferencial (Header):</strong> <code>Authorization: Bearer SEU_TOKEN_DE_ACESSO</code></li>
            <li><strong>Alternativa (Query Parameter):</strong> <code>/rota?token=SEU_TOKEN_DE_ACESSO</code></li>
        </ol>

        <hr>

        <h2>🎬 Endpoints de Listagem e Busca (Saída Limpa)</h2>
        <p>Em caso de sucesso (200 OK), estas rotas retornam o conteúdo diretamente como um <strong>Array JSON</strong> (<code>[...]</code>) contendo os objetos de filme.</p>

        <table>
            <thead>
                <tr>
                    <th>Método</th>
                    <th>Endpoint</th>
                    <th>Descrição</th>
                    <th>Exemplo de Saída</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/</code></td>
                    <td>Retorna uma lista de <strong>todos</strong> os filmes.</td>
                    <td><code>[...]</code> (Array de objetos de filme)</td>
                </tr>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/categorias</code></td>
                    <td>Retorna a lista de todas as categorias disponíveis.</td>
                    <td><code>{"categorias": ["Ação", "Terror", ...]}</code></td>
                </tr>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/&lt;genero&gt;</code></td>
                    <td>Filtra filmes por <strong>Categoria/Gênero</strong> (Ex: <code>/Terror</code>).</td>
                    <td><code>[...]</code> (Array de objetos de filme)</td>
                </tr>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/titulo/&lt;titulo_busca&gt;</code></td>
                    <td>Busca filmes que contenham o título exato ou parcial.</td>
                    <td><code>[...]</code> (Array de objetos de filme)</td>
                </tr>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/ano/&lt;ano_busca&gt;</code></td>
                    <td>Filtra filmes por um <strong>Ano</strong> específico (Ex: <code>/ano/2025</code>).</td>
                    <td><code>[...]</code> (Array de objetos de filme)</td>
                </tr>
            </tbody>
        </table>

        <h3>Estrutura do Objeto de Filme (Retorno)</h3>
        <pre>
[
  {
    "ano": "2025",
    "classificacao": "14",
    "duracao": "96 Min",
    "filme_id": 0,
    "generos": "Comédia, NETFLIX",
    "titulo": "Uma Advogada Brilhante",
    "url_capa": "...",
    "views": "8,990"
    // ... e outros campos não sensíveis
  },
  // ...
]
        </pre>

        <hr>

        <h2>🎥 Acesso à Mídia (Player Proxy)</h2>

        <h3>1. Geração do Link Temporário</h3>
        <p>Use esta rota para obter a URL de streaming seguro. Requer o Token de Acesso à API.</p>
        
        <table>
            <thead>
                <tr>
                    <th>Método</th>
                    <th>Endpoint</th>
                    <th>Descrição</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span class="method get">GET</span></td>
                    <td><code>/titulo/&lt;titulo_busca&gt;/player</code></td>
                    <td>Gera uma URL temporária e mascarada para o player.</td>
                </tr>
            </tbody>
        </table>

        <p><strong>Resposta de Sucesso (Exemplo):</strong></p>
        <pre>
{
  "status": "sucesso",
  "filme": "Nome do Filme",
  "link_temporario": "https://sua-api.vercel.app/player_proxy/ID?temp_token=TOKEN_ASSINADO_AQUI", 
  "expira_em_segundos": 14400 
}
        </pre>

        <div class="note">
            <h4>IMPORTANTE:</h4>
            <p>O <code>link_temporario</code> deve ser usado como <code>src</code> no seu player de vídeo. Ele expira em 4 horas (14400s).</p>
        </div>

        <h3>2. Proxy de Conteúdo Contínuo</h3>
        <p>Endpoint final acessado pelo player. Ele valida o <code>temp_token</code> e transmite o fluxo de mídia (não retorna JSON).</p>
        
        <hr>

        <h2>🚨 Códigos de Erro Comuns</h2>
        <p>Os erros retornam um objeto JSON para facilitar o tratamento.</p>

        <table>
            <thead>
                <tr>
                    <th>Código HTTP</th>
                    <th>Motivo</th>
                    <th>Exemplo de JSON</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>401</code></td>
                    <td>Token de acesso ou temporário inválido/ausente/expirado.</td>
                    <td><code>{"erro": "Acesso negado. O link expirou."}</code></td>
                </tr>
                <tr>
                    <td><code>404</code></td>
                    <td>Nenhum conteúdo encontrado na busca/filtro.</td>
                    <td><code>{"mensagem": "Nenhum conteúdo encontrado...", "filmes": []}</code></td>
                </tr>
            </tbody>
        </table>

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
