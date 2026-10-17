import json
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from str_workflow.seo import article_schema


def test_episode_release_date_is_not_critique_publication_date():
    article = article_schema('Critique', 'Evidence review', 'https://onreason.com/episodes/example/',
                             '2026-01-01', 'Source episode', 'https://example.org/episode')
    assert 'datePublished' not in article
    assert article['isBasedOn']['datePublished'] == '2026-01-01'


def test_public_search_metadata_is_unique_and_archive_is_complete():
    titles, descriptions, urls = set(), set(), set()
    pages = list(Path('docs').glob('**/index.html'))
    for page in pages:
        soup = BeautifulSoup(page.read_text(), 'html.parser')
        title = soup.title.get_text()
        description = soup.select_one('meta[name="description"]')['content']
        assert title not in titles, page
        assert description not in descriptions, page
        assert len(description) <= 160
        titles.add(title)
        descriptions.add(description)
        urls.add(soup.select_one('link[rel="canonical"]')['href'])
        graph = json.loads(soup.select_one('#structured-data').string)['@graph']
        if page == Path('docs/index.html'):
            archive = next(node for node in graph if node['@type'] == 'ItemList')
    sitemap = ElementTree.parse('docs/sitemap.xml')
    locations = {node.text for node in sitemap.findall('.//{*}loc')}
    assert locations == urls
    assert {item['url'] for item in archive['itemListElement']} == {url for url in urls if '/episodes/' in url}
    assert archive['numberOfItems'] == len(archive['itemListElement'])
