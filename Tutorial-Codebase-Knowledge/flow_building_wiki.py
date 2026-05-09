from pocketflow import Flow

from nodes import IdentifyAbstractions
from nodes_building_wiki import (
    FetchDoclingDocuments,
    SafeAnalyzeRelationships,
    ExtractBuildingWikiPages,
    WriteBuildingWiki,
)


def create_building_wiki_flow():
    fetch_docs = FetchDoclingDocuments()
    identify_abstractions = IdentifyAbstractions(max_retries=3, wait=10)
    analyze_relationships = SafeAnalyzeRelationships(max_retries=2, wait=5)
    extract_pages = ExtractBuildingWikiPages(max_retries=3, wait=10)
    write_wiki = WriteBuildingWiki()

    fetch_docs >> identify_abstractions
    identify_abstractions >> analyze_relationships
    analyze_relationships >> extract_pages
    extract_pages >> write_wiki

    return Flow(start=fetch_docs)
