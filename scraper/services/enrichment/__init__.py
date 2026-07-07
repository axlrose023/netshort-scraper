from scraper.services.enrichment.base import DetailParser, Enricher
from scraper.services.enrichment.detail_page import DetailPageEnricher
from scraper.services.enrichment.null import NullEnricher

__all__ = ["DetailPageEnricher", "DetailParser", "Enricher", "NullEnricher"]
