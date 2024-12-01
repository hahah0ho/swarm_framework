from tavily import TavilyClient
import os
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class TavilySearch:
    def __init__(self, API_KEY, domains=["google.com", "naver.com"], k=6):
        self.client = TavilyClient(api_key=API_KEY)
        self.domains = domains
        self.k = k

    def search(self, query: str):
        response = self.client.search(
            query,
            search_depth="advanced",
            max_results=self.k,
            include_domains=self.domains,
            include_raw_content=True,
        )

        search_results = [
            {
                "url": r["url"],
                "content": f'<title>{r["title"]}</title><content>{r["content"]}</content><raw>{r["content"]}</raw>',
            }
            for r in response["results"]
        ]

        return search_results



def search_on_web_1(query: str):
    tavily_tool = TavilySearch(
        API_KEY=TAVILY_API_KEY,
        domains=["google.com"],
        k=6,
    )
    return tavily_tool.search(query)

def search_on_web_2(query: str):
    tavily_tool = TavilySearch(
        API_KEY=TAVILY_API_KEY,
        domains=["naver.com"],
        k=3,
    )
    return tavily_tool.search(query)