from pocketflow import Flow

from nodes_building_wiki import (
    FetchDoclingDocuments,
    ExtractBuildingWikiPages,
    WriteBuildingWiki,
)


class Pass1ExtractBuildingWikiPages(ExtractBuildingWikiPages):
    def prep(self, shared):
        shared.setdefault("abstractions", [])
        shared.setdefault("relationships", {})
        return super().prep(shared)


def create_building_wiki_flow():
    fetch_docs = FetchDoclingDocuments()
    extract_pages = Pass1ExtractBuildingWikiPages(max_retries=3, wait=10)
    write_wiki = WriteBuildingWiki()

    fetch_docs >> extract_pages
    extract_pages >> write_wiki

    return Flow(start=fetch_docs)
