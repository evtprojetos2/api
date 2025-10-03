# ... (rest of the file content before the routes)

# --- ROTA DE PROXY (MANTIDA) ---

# ... (all existing routes and functions) ...

# --- NOVA ROTA DE DOCUMENTAÇÃO ---

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
                    <td>Busca filmes que contenham o título.</td>
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
        <p>Use esta rota para obter o URL de streaming seguro. Requer o Token de Acesso à API.</p>
        
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

# ... (End of file)
