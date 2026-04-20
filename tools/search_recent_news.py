"""
search_recent_news tool
Fetches recent news for a given query (e.g. "DataStax IBM", "ScyllaDB").
The Copywriter calls this twice — once per query — to get current pain and
value signals before writing messages.

Real API path: set NEWS_API_KEY in .env (https://newsapi.org free tier is enough).
Mock fallback: curated realistic stories used when no key is present.
"""

import os
import requests
from crewai.tools import tool


# ---------------------------------------------------------------------------
# Mock news — realistic stories used when NEWS_API_KEY is not set.
# Curated to cover the main angles the Copywriter can choose from:
#   acquisition_uncertainty, performance_cost, migration_simplicity, vendor_independence
# ---------------------------------------------------------------------------

_MOCK_NEWS: dict[str, list[dict]] = {
    "datastax": [
        {
            "title": "IBM Completes DataStax Acquisition, Plans Full Astra DB Integration into IBM Cloud",
            "source": "InfoWorld",
            "date": "2025-05-14",
            "summary": (
                "IBM has finalised its acquisition of DataStax and announced that Astra DB "
                "will be absorbed into IBM Cloud Pak for Data. Enterprise pricing is expected "
                "to align with IBM's standard licensing model in the next renewal cycle."
            ),
        },
        {
            "title": "DataStax Enterprise Customers Report 30–40% Price Increases at First IBM-Era Renewal",
            "source": "The Register",
            "date": "2025-07-02",
            "summary": (
                "Multiple DataStax Enterprise customers told The Register that their first "
                "post-acquisition renewal quotes came in significantly higher than prior years. "
                "IBM cited 'platform unification costs' as the driver."
            ),
        },
        {
            "title": "Key DataStax Engineering Leads Depart Following IBM Integration Announcement",
            "source": "CRN",
            "date": "2025-06-18",
            "summary": (
                "Several senior engineers behind Astra DB's serverless runtime have left the "
                "company. Industry observers note this follows a pattern seen in other IBM "
                "acquisitions where product teams lose autonomy post-integration."
            ),
        },
        {
            "title": "IBM DataStax Roadmap Update Raises Open-Source Commitment Questions",
            "source": "ZDNet",
            "date": "2025-08-05",
            "summary": (
                "IBM's updated DataStax roadmap focuses on enterprise integrations and "
                "IBM Cloud exclusivity. Community contributors expressed concern that "
                "open-source Cassandra improvements will no longer be a priority."
            ),
        },
        {
            "title": "Analysts Flag IBM DataStax as High Vendor Lock-In Risk for Cassandra Workloads",
            "source": "Gartner Research Note",
            "date": "2025-09-10",
            "summary": (
                "Gartner's latest note on Cassandra-compatible databases flags IBM DataStax "
                "as elevated vendor lock-in risk following the acquisition. Analysts recommend "
                "enterprises evaluate alternatives before their next renewal."
            ),
        },
    ],
    "scylladb": [
        {
            "title": "ScyllaDB 6.0 Ships: Raft-Based Topology, 30% Throughput Gain, Zero Downtime Upgrades",
            "source": "InfoQ",
            "date": "2025-06-01",
            "summary": (
                "ScyllaDB 6.0 introduces consistent topology changes via Raft, eliminating "
                "the split-brain risk that plagued earlier versions. Benchmarks show a 30% "
                "throughput improvement on write-heavy workloads."
            ),
        },
        {
            "title": "Booking.com: ScyllaDB Handles 1.2M req/s on 12 Nodes vs 45 Cassandra Nodes",
            "source": "ScyllaDB Summit 2025",
            "date": "2025-04-22",
            "summary": (
                "Booking.com presented migration results at ScyllaDB Summit: the same "
                "workload that required 45 Cassandra nodes now runs on 12 ScyllaDB nodes "
                "with lower p99 latency and a 60% reduction in cloud spend."
            ),
        },
        {
            "title": "ScyllaDB Achieves CQL and SSTable Full Compatibility — Migrations Now Tool-Free",
            "source": "The New Stack",
            "date": "2025-07-15",
            "summary": (
                "ScyllaDB's latest tooling validates full SSTable-level compatibility with "
                "Cassandra 4.x, meaning existing data files, drivers, and client code "
                "require zero changes during migration."
            ),
        },
        {
            "title": "ScyllaDB Cloud Adds EU Sovereign Region and Achieves SOC 2 Type II",
            "source": "Business Wire",
            "date": "2025-08-20",
            "summary": (
                "ScyllaDB Cloud now offers an EU sovereign region with data residency guarantees, "
                "alongside SOC 2 Type II certification. The move targets regulated industries "
                "including fintech, healthcare, and public sector."
            ),
        },
        {
            "title": "Discord Case Study: 100B+ Messages Migrated from Cassandra to ScyllaDB, Cluster Shrinks 75%",
            "source": "Discord Engineering Blog",
            "date": "2025-03-10",
            "summary": (
                "Discord published full migration metrics: moving 100 billion messages from "
                "Cassandra to ScyllaDB reduced their cluster from 177 nodes to 72, cut p99 "
                "read latency by 40%, and eliminated all GC-pause incidents."
            ),
        },
    ],
}


def _query_key(query: str) -> str:
    """Map a free-form query string to a mock news bucket."""
    q = query.lower()
    if "scylladb" in q or "scylla" in q:
        return "scylladb"
    return "datastax"


def _format_articles(articles: list[dict]) -> str:
    lines = []
    for a in articles:
        lines.append(f"[{a.get('date', 'n/a')}] {a['title']} — {a['source']}")
        lines.append(f"  {a['summary']}")
    return "\n\n".join(lines)


def _fetch_real_news(query: str, api_key: str) -> str:
    """Call NewsAPI and return formatted results."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": 5,
        "language": "en",
        "apiKey": api_key,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        articles = [
            {
                "title": a["title"],
                "source": a["source"]["name"],
                "date": a["publishedAt"][:10],
                "summary": a.get("description") or a.get("content") or "",
            }
            for a in data.get("articles", [])
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
        if not articles:
            return f"No recent news found for '{query}'."
        return _format_articles(articles)
    except Exception as exc:
        return f"News API error for '{query}': {exc}"


@tool("search_recent_news")
def search_recent_news(query: str) -> str:
    """
    Search for recent news about a company or topic.
    Call this with 'DataStax IBM' or 'DataStax' for pain signals,
    and with 'ScyllaDB' for value signals.
    Returns a list of recent article headlines and summaries.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if api_key:
        return _fetch_real_news(query, api_key)

    # Mock fallback
    bucket = _query_key(query)
    articles = _MOCK_NEWS[bucket]
    header = f"[MOCK DATA — set NEWS_API_KEY for live results]\nQuery: '{query}'\n\n"
    return header + _format_articles(articles)
