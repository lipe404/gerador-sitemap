from flask import Flask, request, Response, jsonify, render_template
import logging
import os
# from datetime import datetime
from utils.website_scraper import WebsiteScraper
from utils.sitemap_generator import SitemapGenerator

# Configuração do Flask
app = Flask(__name__)

# Configuração de logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Renderiza a página inicial com o formulário."""
    return render_template('index.html')


@app.route('/generate-sitemap', methods=['GET', 'POST'])
def generate_sitemap():
    """
    Endpoint principal para gerar sitemap.xml baseado em website

    Aceita tanto GET quanto POST requests
    Parâmetro: website_url - URL do website

    Returns:
        Response: XML do sitemap ou erro em JSON
    """
    try:
        # Obter URL do website da requisição
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'website_url' not in data:
                return jsonify({
                    'error': 'Campo website_url é obrigatório no JSON'
                }), 400
            website_url = data['website_url']
            max_depth = data.get('max_depth', 3)
            include_images = data.get('include_images', True)
        else:  # GET
            website_url = request.args.get('website_url')
            if not website_url:
                return jsonify({
                    'error': 'Parâmetro website_url é obrigatório'
                }), 400
            max_depth = int(request.args.get('max_depth', 3))
            include_images = request.args.get(
                'include_images', 'true').lower() == 'true'

        logger.info(f"Iniciando geração de sitemap para: {website_url}")

        # Validar URL do website
        if not _is_valid_url(website_url):
            logger.warning(f"URL inválida fornecida: {website_url}")
            return jsonify({
                'error': 'URL inválida. Use o formato: https://exemplo.com'
            }), 400

        # Fazer scraping do website
        scraper = WebsiteScraper(
            max_depth=max_depth, include_images=include_images)
        urls = scraper.scrape_website(website_url)

        if not urls:
            logger.warning(
                f"Nenhuma URL encontrada para o website: {website_url}")
            return jsonify({
                'error': 'Nenhuma página encontrada no website'
            }), 404

        # Gerar sitemap.xml
        sitemap_generator = SitemapGenerator()
        sitemap_xml = sitemap_generator.generate_sitemap(urls)

        logger.info(
            f"Sitemap gerado com sucesso para {website_url} - {
                len(urls)} URLs encontradas")

        # Retornar XML como resposta
        return Response(
            sitemap_xml,
            mimetype='application/xml',
            headers={
                'Content-Disposition': 'attachment; filename=sitemap.xml',
                'Content-Type': 'application/xml; charset=utf-8'
            }
        )

    except Exception as e:
        logger.error(f"Erro ao gerar sitemap: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }), 500


def _is_valid_url(url):
    """
    Valida se a URL é válida

    Args:
        url (str): URL para validar

    Returns:
        bool: True se válida, False caso contrário
    """
    import re
    pattern = r'^https?://[^\s<>"\'()[\]{}]+$'
    return bool(re.match(pattern, url))


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500


if __name__ == '__main__':
    logger.info("Iniciando servidor Flask...")
    app.run(debug=True, host='0.0.0.0', port=5000)
