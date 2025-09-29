import xml.etree.ElementTree as ET
from typing import List, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SitemapGenerator:
    """
    Classe responsável por gerar sitemap.xml válido seguindo o protocolo sitemap.xml
    """

    def __init__(self):
        # Namespace do protocolo sitemap
        self.sitemap_namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"

    def generate_sitemap(self, urls: List[Dict[str, str]]) -> str:
        """
        Gera um sitemap.xml válido baseado na lista de URLs

        Args:
            urls (List[Dict]): Lista de dicionários com informações das URLs

        Returns:
            str: XML do sitemap formatado
        """
        try:
            logger.info(f"Gerando sitemap com {len(urls)} URLs")

            # Criar elemento raiz do sitemap
            urlset = ET.Element("urlset")
            urlset.set("xmlns", self.sitemap_namespace)

            # Adicionar cada URL ao sitemap
            for url_info in urls:
                url_element = self._create_url_element(url_info)
                if url_element is not None:
                    urlset.append(url_element)

            # Converter para string XML formatada
            xml_string = self._format_xml(urlset)

            logger.info("Sitemap gerado com sucesso")
            return xml_string

        except Exception as e:
            logger.error(f"Erro ao gerar sitemap: {str(e)}")
            raise

    def _create_url_element(self, url_info: Dict[str, str]) -> ET.Element:
        """
        Cria um elemento <url> para o sitemap

        Args:
            url_info (Dict): Informações da URL

        Returns:
            ET.Element: Elemento XML da URL
        """
        try:
            # Validar se a URL é válida
            if not url_info.get('url') or not self._is_valid_url(url_info['url']):
                logger.warning(
                    f"URL inválida ignorada: {url_info.get('url', 'N/A')}")
                return None

            # Criar elemento <url>
            url_element = ET.Element("url")

            # Elemento obrigatório <loc>
            loc = ET.SubElement(url_element, "loc")
            loc.text = self._escape_xml(url_info['url'])

            # Elemento opcional <lastmod>
            if url_info.get('lastmod'):
                lastmod = ET.SubElement(url_element, "lastmod")
                lastmod.text = url_info['lastmod']

            # Elemento opcional <changefreq>
            if url_info.get('changefreq'):
                changefreq = ET.SubElement(url_element, "changefreq")
                changefreq.text = url_info['changefreq']

            # Elemento opcional <priority>
            if url_info.get('priority'):
                priority = ET.SubElement(url_element, "priority")
                priority.text = str(url_info['priority'])

            return url_element

        except Exception as e:
            logger.warning(
                f"Erro ao criar elemento URL para {url_info.get('url', 'N/A')}: {str(e)}")
            return None

    def _is_valid_url(self, url: str) -> bool:
        """
        Valida se uma URL é válida para sitemap

        Args:
            url (str): URL para validar

        Returns:
            bool: True se válida, False caso contrário
        """
        import re

        # Regex básica para validação de URL
        url_pattern = r'^https?://[^\s<>"\'()[\]{}]+$'

        if not re.match(url_pattern, url):
            return False

        # Verificar se não é muito longa (limite do protocolo sitemap)
        if len(url) > 2048:
            return False

        return True

    def _escape_xml(self, text: str) -> str:
        """
        Escapa caracteres especiais para XML

        Args:
            text (str): Texto para escapar

        Returns:
            str: Texto escapado
        """
        if not text:
            return ""

        # Escapar caracteres especiais XML
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")

        return text

    def _format_xml(self, root: ET.Element) -> str:
        """
        Formata o XML de forma legível

        Args:
            root (ET.Element): Elemento raiz do XML

        Returns:
            str: XML formatado como string
        """
        # Adicionar indentação para melhor legibilidade
        self._indent_xml(root)

        # Converter para string
        xml_string = ET.tostring(root, encoding='unicode', method='xml')

        # Adicionar declaração XML
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

        return xml_declaration + xml_string

    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """
        Adiciona indentação ao XML para melhor legibilidade

        Args:
            elem (ET.Element): Elemento para indentar
            level (int): Nível de indentação
        """
        indent = "\n" + level * "  "

        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def validate_sitemap(self, xml_content: str) -> Dict[str, any]:
        """
        Valida se o sitemap gerado está correto

        Args:
            xml_content (str): Conteúdo XML do sitemap

        Returns:
            Dict: Resultado da validação
        """
        try:
            # Tentar parsear o XML
            root = ET.fromstring(xml_content)

            # Verificar namespace
            if root.tag != f"{{{self.sitemap_namespace}}}urlset":
                return {
                    'valid': False,
                    'error': 'Namespace do sitemap inválido'
                }

            # Contar URLs
            urls = root.findall(f"{{{self.sitemap_namespace}}}url")
            url_count = len(urls)

            # Verificar limite de URLs (50.000 é o limite do protocolo)
            if url_count > 50000:
                return {
                    'valid': False,
                    'error': f'Muitas URLs no sitemap: {url_count} (máximo: 50.000)'
                }

            # Verificar se todas as URLs têm elemento <loc>
            for url in urls:
                loc = url.find(f"{{{self.sitemap_namespace}}}loc")
                if loc is None or not loc.text:
                    return {
                        'valid': False,
                        'error': 'URL sem elemento <loc> encontrada'
                    }

            return {
                'valid': True,
                'url_count': url_count,
                'message': f'Sitemap válido com {url_count} URLs'
            }

        except ET.ParseError as e:
            return {
                'valid': False,
                'error': f'Erro de parsing XML: {str(e)}'
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Erro na validação: {str(e)}'
            }
