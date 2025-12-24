# Flavortown | Simple Recipe Search

A super clean, subtle, and powerful web application to search for recipes anywhere online, extract the essentials, and manage your cooking life.

## Features
- **Global Recipe Search**: Crawls the web to find recipes from any source.
- **High Performance**: Uses parallel processing (multi-threading) to extract multiple recipes simultaneously, making it 5-10x faster than sequential crawlers.
- **Smart Caching**: Instant results for repeated searches.
- **Clutter-Free Extraction**: Strips away ads, stories, and popups, leaving only ingredients and instructions.
- **Nutritional Info**: Automatically extracts calories and macronutrients when available.
- **Favorites**: Save your favorite recipes to your browser for quick access.
- **Shopping List**: Add ingredients to a persistent shopping list with one click.
- **Print-Friendly**: Beautifully formatted print view for physical copies in the kitchen.
- **Subtle UI**: Designed with a focus on typography and simplicity using Tailwind CSS and Playfair Display.

## Installation

1. Ensure you have Python 3.x installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the web server:
   ```bash
   python app.py
   ```
2. Open your browser to `http://127.0.0.1:5001`.
3. Search for any dish (e.g., "Mushroom Risotto") and enjoy the clean results.

## Dependencies
- `Flask`: Web framework.
- `ddgs`: DuckDuckGo search integration.
- `recipe-scrapers`: Core extraction engine.
- `Tailwind CSS`: For the clean, modern styling.
