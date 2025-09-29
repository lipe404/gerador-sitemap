import requests
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Set
import re
from datetime import datetime
import mimetypes

logger = logging.getLogger(__name__)


class WebsiteScraper:
    """
    Classe responsável por fazer scraping de websites e extrair URLs relevantes
    """

    def __init__(self, max_depth=3, include_images=True, delay=0.5):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.max_depth = max_depth
        self.include_images = include_images
        self.delay = delay
        self.visited_urls = set()
        self.found_urls = set()
        self.base_domain = None

        # Extensões de arquivos para incluir no sitemap
        self.allowed_extensions = {
            '.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.cfm',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
        }

        # Extensões de imagens
        self.image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
            '.ico', '.tiff', '.tif'
        }

    def scrape_website(self, start_url: str) -> List[Dict[str, str]]:
        """
        Faz scraping de um website e extrai todas as URLs relevantes

        Args:
            start_url (str): URL inicial do website

        Returns:
            List[Dict]: Lista de dicionários com informações das URLs
        """
        try:
            # Normalizar URL inicial
            start_url = self._normalize_url(start_url)
            parsed_url = urlparse(start_url)
            self.base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

            logger.info(
                f"Iniciando scraping de {start_url} com profundidade máxima {self.max_depth}")

            # Iniciar scraping recursivo
            self._scrape_recursive(start_url, 0)

            # Converter URLs encontradas para formato do sitemap
            url_list = []
            for url in self.found_urls:
                url_info = {
                    'url': url,
                    'lastmod': self._get_last_modified_date(url),
                    'changefreq': self._determine_change_frequency(url),
                    'priority': self._calculate_priority(url, start_url)
                }
                url_list.append(url_info)

            # Ordenar por prioridade (maior primeiro)
            url_list.sort(key=lambda x: float(x['priority']), reverse=True)

            logger.info(
                f"Scraping concluído: {len(url_list)} URLs encontradas")
            return url_list

        except Exception as e:
            logger.error(
                f"Erro ao fazer scraping do website {start_url}: {str(e)}")
            raise

    def _scrape_recursive(self, url: str, depth: int):
        """
        Faz scraping recursivo de uma URL

        Args:
            url (str): URL para fazer scraping
            depth (int): Profundidade atual
        """
        if depth > self.max_depth or url in self.visited_urls:
            return

        try:
            logger.info(f"Fazendo scraping de {url} (profundidade: {depth})")

            # Marcar como visitada
            self.visited_urls.add(url)

            # Fazer requisição
            response = self._make_request(url)
            if not response or response.status_code != 200:
                return

            # Adicionar URL atual à lista
            self.found_urls.add(url)

            # Verificar se é uma página HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return

            # Parsear HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extrair links
            links = self._extract_links(soup, url)

            # Extrair imagens se solicitado
            if self.include_images:
                images = self._extract_images(soup, url)
                links.update(images)

            # Fazer scraping recursivo dos links encontrados
            for link in links:
                if self._is_same_domain(link) and link not in self.visited_urls:
                    time.sleep(self.delay)  # Rate limiting
                    self._scrape_recursive(link, depth + 1)

        except Exception as e:
            logger.warning(f"Erro ao fazer scraping de {url}: {str(e)}")

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """
        Extrai todos os links de uma página

        Args:
            soup (BeautifulSoup): Objeto BeautifulSoup da página
            base_url (str): URL base da página

        Returns:
            Set[str]: Conjunto de URLs encontradas
        """
        links = set()

        # Links de âncora
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = self._resolve_url(href, base_url)
            if full_url and self._is_valid_page_url(full_url):
                links.add(full_url)

        # Links de formulários
        for form_tag in soup.find_all('form', action=True):
            action = form_tag['action']
            full_url = self._resolve_url(action, base_url)
            if full_url and self._is_valid_page_url(full_url):
                links.add(full_url)

        # Links em elementos link (CSS, etc.)
        for link_tag in soup.find_all('link', href=True):
            href = link_tag['href']
            full_url = self._resolve_url(href, base_url)
            if full_url and self._is_valid_resource_url(full_url):
                links.add(full_url)

        return links

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """
        Extrai todas as imagens de uma página

        Args:
            soup (BeautifulSoup): Objeto BeautifulSoup da página
            base_url (str): URL base da página

        Returns:
            Set[str]: Conjunto de URLs de imagens
        """
        images = set()

        # Imagens em tags img
        for img_tag in soup.find_all('img', src=True):
            src = img_tag['src']
            full_url = self._resolve_url(src, base_url)
            if full_url and self._is_valid_image_url(full_url):
                images.add(full_url)

        # Imagens em srcset
        for img_tag in soup.find_all('img', srcset=True):
            srcset = img_tag['srcset']
            for src_item in srcset.split(','):
                src = src_item.strip().split()[0]
                full_url = self._resolve_url(src, base_url)
                if full_url and self._is_valid_image_url(full_url):
                    images.add(full_url)

        # Imagens de fundo em CSS inline
        for element in soup.find_all(style=True):
            style = element['style']
            bg_images = re.findall(
                r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
            for bg_image in bg_images:
                full_url = self._resolve_url(bg_image, base_url)
                if full_url and self._is_valid_image_url(full_url):
                    images.add(full_url)

        return images

    def _resolve_url(self, url: str, base_url: str) -> str:
        """
        Resolve uma URL relativa para absoluta

        Args:
            url (str): URL para resolver
            base_url (str): URL base

        Returns:
            str: URL absoluta ou None se inválida
        """
        try:
            if not url or url.startswith('#') or url.startswith('javascript:') or url.startswith('mailto:'):
                return None

            # Resolver URL relativa
            resolved_url = urljoin(base_url, url)

            # Normalizar URL
            return self._normalize_url(resolved_url)

        except Exception:
            return None

    def _normalize_url(self, url: str) -> str:
        """
        Normaliza uma URL removendo fragmentos e parâmetros desnecessários

        Args:
            url (str): URL para normalizar

        Returns:
            str: URL normalizada
        """
        try:
            parsed = urlparse(url)

            # Remover fragmento
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remover fragmento
            ))

            # Remover trailing slash para diretórios (exceto root)
            if normalized.endswith('/') and len(parsed.path) > 1:
                normalized = normalized[:-1]

            return normalized

        except Exception:
            return url

    def _is_same_domain(self, url: str) -> bool:
        """
        Verifica se uma URL pertence ao mesmo domínio

        Args:
            url (str): URL para verificar

        Returns:
            bool: True se mesmo domínio, False caso contrário
        """
        try:
            parsed_url = urlparse(url)
            url_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            return url_domain == self.base_domain
        except Exception:
            return False

    def _is_valid_page_url(self, url: str) -> bool:
        """
        Verifica se uma URL é uma página válida

        Args:
            url (str): URL para verificar

        Returns:
            bool: True se válida, False caso contrário
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()

            # Verificar extensão
            if any(path.endswith(ext) for ext in self.allowed_extensions):
                return True

            # URLs sem extensão (provavelmente páginas dinâmicas)
            if '.' not in path.split('/')[-1]:
                return True

            return False

        except Exception:
            return False

    def _is_valid_resource_url(self, url: str) -> bool:
        """
        Verifica se uma URL é um recurso válido (CSS, JS, etc.)

        Args:
            url (str): URL para verificar

        Returns:
            bool: True se válida, False caso contrário
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()

            # Recursos que podem ser úteis no sitemap
            resource_extensions = {'.css', '.js', '.xml', '.txt', '.pdf'}

            return any(path.endswith(ext) for ext in resource_extensions)

        except Exception:
            return False

    def _is_valid_image_url(self, url: str) -> bool:
        """
        Verifica se uma URL é uma imagem válida

        Args:
            url (str): URL para verificar

        Returns:
            bool: True se válida, False caso contrário
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()

            return any(path.endswith(ext) for ext in self.image_extensions)

        except Exception:
            return False

    def _make_request(self, url: str) -> requests.Response:
        """
        Faz uma requisição HTTP com tratamento de erros

        Args:
            url (str): URL para requisição

        Returns:
            requests.Response: Resposta da requisição ou None em caso de erro
        """
        try:
            response = self.session.get(url, timeout=10, allow_redirects=True)
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erro na requisição para {url}: {str(e)}")
            return None

    def _get_last_modified_date(self, url: str) -> str:
        """
        Obtém a data de última modificação de uma URL

        Args:
            url (str): URL para verificar

        Returns:
            str: Data no formato ISO 8601
        """
        try:
            response = self.session.head(url, timeout=5)
            if response and 'Last-Modified' in response.headers:
                import email.utils
                last_modified = response.headers['Last-Modified']
                dt = email.utils.parsedate_to_datetime(last_modified)
                return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
        except:
            pass

        # Data atual como fallback
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')

    def _determine_change_frequency(self, url: str) -> str:
        """
        Determina a frequência de mudança de uma URL

        Args:
            url (str): URL para analisar

        Returns:
            str: Frequência de mudança
        """
        path = urlparse(url).path.lower()

        # Páginas que mudam frequentemente
        if any(keyword in path for keyword in ['/blog/', '/news/', '/posts/', '/articles/']):
            return 'daily'

        # Páginas de produtos ou serviços
        if any(keyword in path for keyword in ['/products/', '/services/', '/portfolio/']):
            return 'weekly'

        # Imagens e recursos estáticos
        if any(path.endswith(ext) for ext in self.image_extensions):
            return 'yearly'

        # Páginas estáticas
        if any(keyword in path for keyword in ['/about/', '/contact/', '/privacy/', '/terms/']):
            return 'monthly'

        # Página inicial
        if path in ['/', '/index.html', '/index.php']:
            return 'weekly'

        # Default
        return 'monthly'

    def _calculate_priority(self, url: str, start_url: str) -> str:
        """
        Calcula a prioridade de uma URL

        Args:
            url (str): URL para analisar
            start_url (str): URL inicial do site

        Returns:
            str: Prioridade (0.0 a 1.0)
        """
        # Página inicial tem prioridade máxima
        if url == start_url or urlparse(url).path in ['/', '/index.html', '/index.php']:
            return '1.0'

        path = urlparse(url).path.lower()

        # Páginas importantes
        if any(keyword in path for keyword in ['/about/', '/contact/', '/services/', '/products/']):
            return '0.8'

        # Blog e conteúdo
        if any(keyword in path for keyword in ['/blog/', '/news/', '/articles/']):
            return '0.7'

        # Imagens têm prioridade baixa
        if any(path.endswith(ext) for ext in self.image_extensions):
            return '0.3'

        # Recursos estáticos
        if any(path.endswith(ext) for ext in ['.css', '.js', '.pdf']):
            return '0.4'

        # Calcular prioridade baseada na profundidade
        depth = len([p for p in path.split('/') if p])
        if depth <= 1:
            return '0.9'
        elif depth <= 2:
            return '0.7'
        elif depth <= 3:
            return '0.6'
        else:
            return '0.5'
