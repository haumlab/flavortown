from flask import Flask, render_template, request, jsonify
from ddgs import DDGS
from recipe_scrapers import scrape_me
import requests
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
import functools
import sqlite3
import json
import os
import random
import re
from urllib.parse import urlparse

app = Flask(__name__)


DB_PATH = 'recipe_cache.db'
MAX_QUERY_LENGTH = 160
MAX_URL_LENGTH = 500
SUPPORTED_DOMAINS = [
    'allrecipes.com', 'simplyrecipes.com', 'foodnetwork.com',
    'bonappetit.com', 'epicurious.com', 'bettycrocker.com',
    'kingarthurbaking.com', 'delish.com', 'thepioneerwoman.com',
    'seriouseats.com', 'marthastewart.com', 'food.com', '101cookbooks.com',
    'recipetineats.com', 'bbcgoodfood.com', 'tasty.co', 'myrecipes.com',
    'cookinglight.com', 'yummly.com'
]
TRUSTED_DOMAINS = frozenset(SUPPORTED_DOMAINS)
QUERY_PATTERN = re.compile(r"^[\w\s,.'-]+$")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                query TEXT PRIMARY KEY,
                results TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def normalize_query(query: str) -> str:
    return ' '.join(query.split())


def is_valid_query(query: str) -> bool:
    if not query or len(query) > MAX_QUERY_LENGTH:
        return False
    return bool(QUERY_PATTERN.match(query))


def is_valid_url(url: str) -> bool:
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    if '\n' in url or '\r' in url:
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False
    netloc = parsed.netloc.split(':')[0].lower()
    return any(netloc == domain or netloc.endswith(f'.{domain}') for domain in TRUSTED_DOMAINS)

def get_cached_recipes(query):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT results FROM cache WHERE query = ?', (query,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        logging.error(f"Cache read error: {e}")
    return None

def set_cached_recipes(query, recipes):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT OR REPLACE INTO cache (query, results) VALUES (?, ?)',
                         (query, json.dumps(recipes)))
    except Exception as e:
        logging.error(f"Cache write error: {e}")

init_db()

logging.basicConfig(level=logging.INFO)

def search_recipes(query, num_results=10):
    search_query = f"{query} recipe"
    urls = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=30))
            
            priority_urls = []
            other_urls = []
            
            for r in results:
                url = r['href']
                if any(domain in url for domain in SUPPORTED_DOMAINS):
                    priority_urls.append(url)
                elif not any(domain in url for domain in ['youtube.com', 'facebook.com', 'instagram.com', 'pinterest.com', 'tiktok.com']):
                    other_urls.append(url)
            
            urls = priority_urls + other_urls
                        
    except Exception as e:
        logging.error(f"Error during search: {e}")
    
    if not urls:
        urls = search_allrecipes(query, num_results)
    
    return urls[:20]

def search_allrecipes(query, num_results=6):
    search_url = f"https://www.allrecipes.com/search?q={query.replace(' ', '+')}"
    urls = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'allrecipes.com/recipe/' in href and href not in urls:
                urls.append(href)
                if len(urls) >= num_results:
                    break
    except Exception as e:
        logging.error(f"Error during AllRecipes search: {e}")
    return urls

def extract_recipe(url):
    try:
        scraper = scrape_me(url)
        
        instructions = scraper.instructions()
        if isinstance(instructions, str):
            instructions = [s.strip() for s in instructions.split('\n') if s.strip()]

        nutrients = None
        try:
            nutrients = scraper.nutrients()
        except Exception:
            pass

        recipe_data = {
            "title": scraper.title(),
            "total_time": scraper.total_time(),
            "yields": scraper.yields(),
            "ingredients": scraper.ingredients(),
            "instructions": instructions,
            "image": scraper.image(),
            "host": scraper.host(),
            "url": url,
            "nutrients": nutrients
        }
        return recipe_data
    except Exception as e:
        logging.error(f"Could not extract recipe from {url}: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json
    raw_query = data.get('query', '')
    if not isinstance(raw_query, str):
        return jsonify({"error": "Query must be text"}), 400

    query = normalize_query(raw_query.lower())
    if not is_valid_query(query):
        return jsonify({"error": "Invalid query"}), 400
    
    cached_results = get_cached_recipes(query)
    if cached_results:
        logging.info(f"Persistent cache hit for: {query}")
        return jsonify(cached_results)

    urls = search_recipes(query)
    if not urls:
        return jsonify([])

    recipes = []
    candidates = urls[:12] 
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(extract_recipe, candidates))
        
        for r in results:
            if r:
                recipes.append(r)
                if len(recipes) >= 8:
                    break
    
    if recipes:
        set_cached_recipes(query, recipes)
                
    return jsonify(recipes)

@app.route('/api/extract', methods=['POST'])
def api_extract():
    data = request.json
    raw_url = data.get('url')
    if not isinstance(raw_url, str):
        return jsonify({"error": "URL must be text"}), 400

    if not is_valid_url(raw_url):
        return jsonify({"error": "Invalid URL"}), 400
    url = raw_url
    
    recipe = extract_recipe(url)
    if recipe:
        return jsonify(recipe)
    return jsonify({"error": "Could not extract recipe"}), 404

@app.route('/api/random', methods=['GET'])
def api_random():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT results FROM cache ORDER BY RANDOM() LIMIT 1')
            row = cursor.fetchone()
            if row:
                recipes = json.loads(row[0])
                if recipes:
                    return jsonify(random.choice(recipes))
    except Exception as e:
        logging.error(f"Random recipe error: {e}")
    return jsonify({"error": "No cached recipes found"}), 404

if __name__ == '__main__':

    app.run(debug=True, port=5001)