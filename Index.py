from flask import Flask, request, jsonify
import requests
import re
import math
import concurrent.futures
import datetime

app = Flask(__name__)

# ================== CONFIG ==================
TMDB_API_KEY = "6360eb433f3020d94a5de4f0fb52c720"
CURL_TIMEOUT = 10
CURL_CONNECT_TIMEOUT = 5

# ================== HELPERS ==================
def http_get_json(url, timeout=CURL_TIMEOUT):
    """Realiza uma requisição GET e retorna JSON."""
    try:
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; IPTV-Collector/1.0)"
        })
        response.raise_for_status()  # Lança exceção para erros HTTP 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"_error": str(e), "_raw": response.text if response.text else None}

def iconv_safe(s):
    """Remove acentos e caracteres especiais, simulando iconv."""
    if not s:
        return ""
    s = str(s)
    s = re.sub(r'[áàãâä]', 'a', s, flags=re.IGNORECASE)
    s = re.sub(r'[éèêë]', 'e', s, flags=re.IGNORECASE)
    s = re.sub(r'[íìîï]', 'i', s, flags=re.IGNORECASE)
    s = re.sub(r'[óòõôö]', 'o', s, flags=re.IGNORECASE)
    s = re.sub(r'[úùûü]', 'u', s, flags=re.IGNORECASE)
    s = re.sub(r'[ç]', 'c', s, flags=re.IGNORECASE)
    return s.encode('ascii', 'ignore').decode('utf-8')

def normalize_title(s):
    """Normaliza o título para comparação."""
    s = iconv_safe(s)
    s = s.lower()
    s = s.replace('&', ' ').replace('+', ' ')
    s = re.sub(r'[^\w\s]', ' ', s)
    stop_words = [
        'a', 'o', 'os', 'as', 'de', 'da', 'do', 'das', 'dos', 'the', 'and', 'e',
        'um', 'uma', 'para', 'por', 'com', 'sem', 'em', 'na', 'no', 'nos', 'nas'
    ]
    tokens = s.split()
    tokens = [t for t in tokens if t and t not in stop_words]
    return ' '.join(tokens)

def clean_query_title(title):
    """Limpa o título para busca (remove tags e ruído comum)."""
    t = str(title).strip()
    t = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', ' ', t)
    t = re.sub(r'\b(temporada|season|dublado|legendado|dual|nacional|original|completo|torrent|1080p|720p|4k|s\d{1,2}e?\d{0,2})\b', ' ', t, flags=re.I)
    t = re.sub(r'\b(temporada|season)\b.*$', ' ', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def guess_year_from_title(title):
    """Tenta extrair um ano do título."""
    match = re.search(r'\b(19|20)\d{2}\b', str(title))
    if match:
        year = int(match.group(0))
        current_year = int(datetime.datetime.now().year)
        if 1900 <= year <= current_year + 1:
            return year
    return None

def tmdb_search_with_lang(title, lang, api_key, year=None, timeout=CURL_TIMEOUT):
    """Busca no TMDb com idioma e (opcional) ano."""
    url = f"https://api.themoviedb.org/3/search/tv?api_key={api_key}&language={lang}&query={requests.utils.quote(title)}"
    if year:
        url += f"&first_air_date_year={year}"
    return http_get_json(url, timeout)

def tmdb_search_series(title, api_key):
    """Estratégia de busca robusta."""
    clean_title = clean_query_title(title)
    year_guess = guess_year_from_title(title)

    candidates = []
    
    candidates.append(tmdb_search_with_lang(title, 'pt-BR', api_key, year_guess))
    candidates.append(tmdb_search_with_lang(title, 'en-US', api_key, year_guess))
    if clean_title != title:
        candidates.append(tmdb_search_with_lang(clean_title, 'pt-BR', api_key, year_guess))
        candidates.append(tmdb_search_with_lang(clean_title, 'en-US', api_key, year_guess))
    if year_guess:
        candidates.append(tmdb_search_with_lang(clean_title, 'pt-BR', api_key))
        candidates.append(tmdb_search_with_lang(clean_title, 'en-US', api_key))

    for res in candidates:
        if res and 'results' in res and res['results']:
            return res

    return candidates[-1] if candidates else {"results": []}

def score_candidate(query, cand, year_guess=None):
    """Calcula o escore de similaridade."""
    qnorm = normalize_title(query)
    name = normalize_title(cand.get('name', ''))
    oname = normalize_title(cand.get('original_name', ''))

    p1 = 0
    if name and qnorm:
        p1 = similar(qnorm, name) * 100

    p2 = 0
    if oname and qnorm:
        p2 = similar(qnorm, oname) * 100

    sim = max(p1, p2)
    pop = float(cand.get('popularity', 0))
    score = sim * 1.2 + pop

    if year_guess and cand.get('first_air_date'):
        try:
            y = int(cand['first_air_date'][:4])
            if y > 0:
                score -= abs(y - year_guess) * 2.0
        except (ValueError, IndexError):
            pass

    return score

def similar(a, b):
    """Calcula a similaridade entre duas strings."""
    if not a or not b: return 0.0
    return sum(a[i] == b[i] for i in range(min(len(a), len(b)))) / max(len(a), len(b))

def tmdb_get_details_series(tv_id, api_key):
    """Obtém detalhes da série no TMDb."""
    url = f"https://api.themoviedb.org/3/tv/{tv_id}?api_key={api_key}&language=pt-BR&append_to_response=credits,videos,content_ratings"
    return http_get_json(url)

def tmdb_get_seasons_parallel(tv_id, seasons, api_key):
    """Obtém detalhes das temporadas em paralelo."""
    urls = []
    for s in seasons:
        sn = int(s.get('season_number', 0))
        if sn <= 0: continue
        urls.append(f"https://api.themoviedb.org/3/tv/{tv_id}/season/{sn}?api_key={api_key}&language=pt-BR")
    
    responses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(requests.get, url, timeout=CURL_TIMEOUT): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                resp = future.result()
                resp.raise_for_status()
                sn = int(url.split('/')[-1].split('?')[0])
                responses[sn] = resp.json()
            except requests.exceptions.RequestException:
                pass
    return responses

def get_classification_series(details):
    """Extrai a classificação indicativa."""
    ratings = details.get('content_ratings', {}).get('results', [])
    for r in ratings:
        if r.get('iso_3166_1') == 'BR':
            return r.get('rating', "")
    return ratings[0].get('rating', "") if ratings else ""

def xtream_extract_from_player_api(iptv_stream_url):
    """Extrai domínio e credenciais do iptv_stream_url."""
    out = {'domain': 'http://sinalprivado.info', 'username': '430214', 'password': '430214'}
    if not iptv_stream_url:
        return out
    
    from urllib.parse import urlparse, parse_qs
    u = urlparse(iptv_stream_url)
    if u.scheme and u.netloc:
        out['domain'] = f"{u.scheme}://{u.netloc}"
    if u.query:
        q = parse_qs(u.query)
        out['username'] = q.get('username', [out['username']])[0]
        out['password'] = q.get('password', [out['password']])[0]
    return out

def iptv_build_episode_id_map(iptv_stream_url, timeout=CURL_TIMEOUT):
    """Cria mapa season_episode => id_original do IPTV."""
    data = http_get_json(iptv_stream_url, timeout)
    episode_map = {}
    if data and 'episodes' in data and isinstance(data['episodes'], dict):
        for season_key, episodes in data['episodes'].items():
            if not isinstance(episodes, list): continue
            for ep in episodes:
                snum = int(ep.get('season', season_key) or 0)
                enum = int(ep.get('episode_num', 0) or 0)
                ep_id = ep.get('id')
                if ep_id and enum > 0:
                    episode_map[f"{snum}_{enum}"] = ep_id
    return episode_map

# ================== ROTA DA API ==================
@app.route('/series_info')
def series_info():
    """Endpoint para obter informações detalhadas da série."""
    nome = request.args.get('nome', '')
    series_id = request.args.get('series_id', '')
    iptv_category_id = request.args.get('category_id', '')
    iptv_poster = request.args.get('iptv_poster', '')
    iptv_stream_url = request.args.get('iptv_stream_url', '')

    if not nome or not series_id:
        return jsonify({"error": "Parâmetros obrigatórios ausentes (nome, series_id)"}), 400

    # Busca no TMDb
    search_results = tmdb_search_series(nome, TMDB_API_KEY)
    results = search_results.get('results', [])

    if not results:
        return jsonify({
            "error": "Série não encontrada no TMDb",
            "debug": {
                "query_enviada": nome,
                "query_limpa": clean_query_title(nome)
            }
        }), 404

    # Encontrando o melhor candidato
    year_guess = guess_year_from_title(nome)
    best_candidate = max(results, key=lambda c: score_candidate(nome, c, year_guess), default=None)

    if not best_candidate or not best_candidate.get('id'):
        return jsonify({"error": "Não foi possível determinar o melhor resultado no TMDb"}), 500

    # Detalhes da série
    details = tmdb_get_details_series(best_candidate['id'], TMDB_API_KEY)
    if details.get('_error'):
        return jsonify({"error": "Falha ao obter detalhes da série no TMDb", "tmdb_error": details['_error']}), 500

    # Trailer
    trailer = ""
    for v in details.get('videos', {}).get('results', []):
        if v.get('type') == 'Trailer' and v.get('key'):
            trailer = f"https://www.youtube.com/watch?v={v['key']}"
            break

    # URL IPTV automática (se não enviada)
    if not iptv_stream_url:
        iptv_stream_url = f"http://sinalprivado.info/player_api.php?username=430214&password=430214&action=get_series_info&series_id={series_id}"

    # Carrega config Xtream e mapa de IDs de episódio
    xtream_conf = xtream_extract_from_player_api(iptv_stream_url)
    iptv_episode_map = iptv_build_episode_id_map(iptv_stream_url)

    # Mapa de gêneros para fallback
    tmdb_genres_map = {
        10759: "Ação & Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário",
        18: "Drama", 10751: "Família", 10762: "Infantil", 9648: "Mistério", 10763: "Notícias",
        10764: "Reality", 10765: "Ficção Científica & Fantasia", 10766: "Soap", 10767: "Talk",
        10768: "Guerra & Política", 37: "Faroeste"
    }
    
    if not details.get('genres') and best_candidate.get('genre_ids'):
        details['genres'] = [{"id": gid, "name": tmdb_genres_map.get(gid, "Desconhecido")} for gid in best_candidate['genre_ids']]

    # Montagem do JSON
    serie = {
        "iptv_series_id": series_id,
        "iptv_category_id": iptv_category_id,
        "iptv_name": nome,
        "iptv_poster": iptv_poster or "",
        "titulo_usado": nome,
        "tmdb_id": details.get('id', 0),
        "tmdb_name": details.get('name', ""),
        "tmdb_first_air_date": details.get('first_air_date', ""),
        "tmdb_popularity": details.get('popularity', 0),
        "tmdb_vote_count": details.get('vote_count', 0),
        "titulo": details.get('name', ""),
        "titulo_original": details.get('original_name', ""),
        "sinopse": details.get('overview', "Descrição não disponível"),
        "nota": details.get('vote_average', 0),
        "lancamento": details.get('first_air_date', ""),
        "numero_temporadas": details.get('number_of_seasons', 0),
        "numero_episodios": details.get('number_of_episodes', 0),
        "classificacao_indicativa": get_classification_series(details),
        "poster": f"https://image.tmdb.org/t/p/w500{details['poster_path']}" if details.get('poster_path') else "",
        "backdrop": f"https://image.tmdb.org/t/p/w500{details['backdrop_path']}" if details.get('backdrop_path') else "",
        "trailer": trailer
    }

    generos = [g.get('name') for g in details.get('genres', []) if g.get('name')]
    serie['generos'] = ", ".join(generos)

    elenco = []
    cast_list = details.get('credits', {}).get('cast', [])[:10]
    for c in cast_list:
        elenco.append({
            "name": c.get('name', ""),
            "foto": f"https://image.tmdb.org/t/p/w200{c['profile_path']}" if c.get('profile_path') else ""
        })
    serie['elenco'] = elenco

    temporadas = []
    for s in details.get('seasons', []):
        temporadas.append({
            "season_number": s.get('season_number', 0),
            "name": s.get('name', ""),
            "episodios_count": s.get('episode_count', 0),
            "poster": f"https://image.tmdb.org/t/p/w500{s['poster_path']}" if s.get('poster_path') else ""
        })

    episodios = []
    season_details_all = tmdb_get_seasons_parallel(details['id'], details.get('seasons', []), TMDB_API_KEY)
    for season_number, season_data in season_details_all.items():
        for ep in season_data.get('episodes', []):
            ep_num = ep.get('episode_number', 0)
            iptv_id = iptv_episode_map.get(f"{season_number}_{ep_num}")
            play_url = ""
            if iptv_id:
                play_url = f"{xtream_conf['domain']}/series/{xtream_conf['username']}/{xtream_conf['password']}/{iptv_id}.mp4"
            
            episodios.append({
                "season_number": season_number,
                "episode_number": ep_num,
                "name": ep.get('name', ""),
                "overview": ep.get('overview', ""),
                "air_date": ep.get('air_date', ""),
                "still_path": f"https://image.tmdb.org/t/p/w300{ep['still_path']}" if ep.get('still_path') else "",
                "url": play_url
            })

    response = {
        "serie": serie,
        "temporadas": temporadas,
        "episodios": episodios
    }

    return jsonify(response)
