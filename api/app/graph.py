"""Link-graph inference, after SiNMULI (Gayen, Mondal, Jana, arXiv:2608.19190).

"Tell me who links to you and I'll tell you who you are." Sites are nodes, hyperlinks between
sites are directed edges, and every edge gets a sign from the site it starts at:

    +1  the linking site is known to be honest
    -1  the linking site is known to be a scam (or the link ends at one)
     0  the linking site is unknown, so the sign is unknown too

Following the paper's Algorithm 2:
1. Take the triangles (i -> j, j -> k, i -> k) that have exactly one unknown edge and exactly one
   unlabeled site, and fill in the unknown sign so the three signs multiply to +1 (balance).
2. Label each unlabeled site by its incoming links: honest if more than 51% are positive,
   a scam if more than 51% are negative, otherwise abstain.

Only the scanned site's neighbourhood is built (who it links to, who links to it, and the links
among those), never the whole web. The data comes from the page library, so a brand-new domain
often has no known links at all, and then the graph says nothing. That is expected, and the
report says so.
"""

import logging
from collections import defaultdict

import networkx as nx
import psycopg
from pydantic import BaseModel

from app.analysis.brands import official_name
from app.analysis.toplist import toplist
from app.blacklists.lists import known

log = logging.getLogger("linklens.graph")

MAJORITY = 0.51
MAX_OUT = 60
MAX_IN = 120
MAX_MAP_NODES = 45
POPULAR_RANK = 100_000


class GraphNode(BaseModel):
    id: str  # a site name, shown defanged
    label: int = 0  # +1 honest, -1 scam, 0 unknown
    role: str = "neighbour"  # scanned | links_to | linked_from | both | neighbour
    why: str | None = None  # why it has that label


class GraphEdge(BaseModel):
    source: str
    target: str
    sign: int = 0
    inferred: bool = False  # the sign was filled in by the balance rule


class GraphResult(BaseModel):
    # labelled   the neighbours gave the site a label
    # abstained  links exist but don't agree (or too few are known)
    # no_links   no known site links to it
    # skipped    nothing to build a graph from
    # unavailable  the page library couldn't be read
    status: str = "no_links"
    label: str | None = None  # "benign" | "malicious"
    note: str | None = None
    positive_in: int = 0
    negative_in: int = 0
    unknown_in: int = 0
    links_out: int = 0
    scam_links_out: int = 0  # links from this site to known scam sites
    triads: int = 0  # triangles the balance rule could use
    inferred_edges: int = 0
    in_degree: int = 0
    out_degree: int = 0
    pagerank: float = 0.0
    eigenvector: float = 0.0
    clustering: float = 0.0
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


def edge_sign(source_label: int, target_label: int) -> int:
    """The paper's starting signs: honest -> honest is +1, anything involving a known scam is -1,
    and a link from an unknown site is unknown."""
    if source_label == 0:
        return 0
    if source_label < 0 or target_label < 0:
        return -1
    return 1


def infer_signs(graph: nx.DiGraph) -> tuple[int, int]:
    """Fill in unknown edge signs with the balance rule. Returns (triangles used, edges inferred).

    A triangle here is i -> j, j -> k, i -> k. It is used when exactly one of its edges is unknown
    and exactly one of its sites is unlabeled. The unknown sign is whatever makes the product +1.
    When triangles disagree about an edge, the majority wins; a tie leaves it unknown (the paper's
    fallback to weak balance, which only asks that no triangle be made negative).
    """
    used: set[tuple[str, str, str]] = set()
    inferred = 0
    changed = True
    while changed:
        changed = False
        votes: dict[tuple[str, str], int] = defaultdict(int)
        for j in graph.nodes:
            for i in graph.predecessors(j):
                for k in graph.successors(j):
                    if i == k or not graph.has_edge(i, k):
                        continue
                    triangle = [(i, j), (j, k), (i, k)]
                    signs = [graph.edges[e]["sign"] for e in triangle]
                    unlabeled = sum(1 for n in (i, j, k) if graph.nodes[n]["label"] == 0)
                    if signs.count(0) != 1 or unlabeled != 1:
                        continue
                    unknown = triangle[signs.index(0)]
                    product = 1
                    for s in signs:
                        product *= s or 1
                    votes[unknown] += product  # the sign that makes the triangle's product +1
                    used.add((i, j, k))
        for edge, vote in votes.items():
            if vote != 0 and graph.edges[edge]["sign"] == 0:
                graph.edges[edge]["sign"] = 1 if vote > 0 else -1
                graph.edges[edge]["inferred"] = True
                inferred += 1
                changed = True
    return len(used), inferred


def vote(graph: nx.DiGraph, node: str) -> tuple[int, int, int]:
    """Incoming links to a site, counted as (positive, negative, unknown)."""
    positive = negative = unknown = 0
    for source in graph.predecessors(node):
        sign = graph.edges[source, node]["sign"]
        if sign > 0:
            positive += 1
        elif sign < 0:
            negative += 1
        else:
            unknown += 1
    return positive, negative, unknown


def majority_label(positive: int, negative: int) -> int:
    """The 51% rule. Ties and near-ties abstain (0)."""
    total = positive + negative
    if total == 0:
        return 0
    if positive / total > MAJORITY:
        return 1
    if negative / total > MAJORITY:
        return -1
    return 0


def site_label(site: str, library: dict[str, tuple[bool, bool]]) -> tuple[int, str | None]:
    """What is already known about a site, from the page library, the phishing lists, the brand
    list, and the popularity list. Conflicting evidence means unknown."""
    scam, honest = library.get(site, (False, False))
    listed = known.has_domain(site) is not None
    popular = toplist.rank(site) is not None and toplist.rank(site) <= POPULAR_RANK
    official = official_name(site, site) is not None
    if (scam or listed) and not (honest or popular or official):
        return -1, "on a phishing list" if listed else "known scam pages"
    if (honest or popular or official) and not (scam or listed):
        return 1, "a brand's real site" if official else "a popular site" if popular else "known honest pages"
    return 0, None


def build(
    site: str,
    out_links: list[str],
    in_links: list[str],
    neighbour_links: dict[str, list[str]],
    library: dict[str, tuple[bool, bool]],
) -> nx.DiGraph:
    """The scanned site's neighbourhood as a signed directed graph. The scanned site itself is
    always left unlabeled, because its label is the question."""
    graph = nx.DiGraph()
    graph.add_node(site, label=0, why=None)
    members = {site, *out_links[:MAX_OUT], *in_links[:MAX_IN]}
    for n in members - {site}:
        label, why = site_label(n, library)
        graph.add_node(n, label=label, why=why)

    def link(a: str, b: str) -> None:
        if a != b and a in members and b in members:
            sign = edge_sign(graph.nodes[a]["label"], graph.nodes[b]["label"])
            graph.add_edge(a, b, sign=sign, inferred=False)

    for target in out_links[:MAX_OUT]:
        link(site, target)
    for source in in_links[:MAX_IN]:
        link(source, site)
    for source, targets in neighbour_links.items():
        for target in targets:
            link(source, target)
    return graph


def judge(site: str, graph: nx.DiGraph) -> GraphResult:
    triads, inferred = infer_signs(graph)
    positive, negative, unknown = vote(graph, site)
    label = majority_label(positive, negative)
    out = list(graph.successors(site))
    scam_out = sum(1 for n in out if graph.nodes[n]["label"] < 0)
    result = GraphResult(
        positive_in=positive,
        negative_in=negative,
        unknown_in=unknown,
        links_out=len(out),
        scam_links_out=scam_out,
        triads=triads,
        inferred_edges=inferred,
        in_degree=graph.in_degree(site),
        out_degree=graph.out_degree(site),
    )
    known_in = positive + negative
    if known_in == 0:
        result.status = "no_links"
        result.note = (
            "No known site links to this one, so the link graph has nothing to say. "
            "That is normal for new domains."
        )
    elif label > 0:
        result.status, result.label = "labelled", "benign"
        result.note = f"{positive} of {known_in} known sites that link here are honest sites."
    elif label < 0:
        result.status, result.label = "labelled", "malicious"
        result.note = f"{negative} of {known_in} known sites that link here are scam sites."
    else:
        result.status = "abstained"
        result.note = (
            f"Sites that link here don't agree ({positive} honest, {negative} scam), "
            "so the link graph makes no call."
        )
    if scam_out:
        result.note += f" It links to {scam_out} known scam {'site' if scam_out == 1 else 'sites'}."

    if graph.number_of_edges():
        try:
            result.pagerank = round(nx.pagerank(graph, max_iter=100)[site], 5)
        except Exception:
            result.pagerank = 0.0
        try:
            scores = nx.eigenvector_centrality(graph.to_undirected(), max_iter=200, tol=1e-4)
            result.eigenvector = round(scores[site], 5)
        except Exception:
            result.eigenvector = 0.0
        result.clustering = round(nx.clustering(graph.to_undirected(), site), 4)

    result.nodes, result.edges = _for_map(site, graph)
    return result


def _for_map(site: str, graph: nx.DiGraph) -> tuple[list[GraphNode], list[GraphEdge]]:
    """A trimmed copy for the network map: the scanned site, then labeled neighbours first."""
    out_set, in_set = set(graph.successors(site)), set(graph.predecessors(site))
    others = sorted(
        (n for n in graph.nodes if n != site),
        key=lambda n: (graph.nodes[n]["label"] == 0, n not in in_set, n),
    )[: MAX_MAP_NODES - 1]
    keep = {site, *others}

    def role(n: str) -> str:
        if n == site:
            return "scanned"
        if n in out_set and n in in_set:
            return "both"
        return "links_to" if n in out_set else "linked_from" if n in in_set else "neighbour"

    nodes = [
        GraphNode(id=n, label=graph.nodes[n]["label"], role=role(n), why=graph.nodes[n].get("why"))
        for n in [site, *others]
    ]
    edges = [
        GraphEdge(source=a, target=b, sign=d["sign"], inferred=d.get("inferred", False))
        for a, b, d in graph.edges(data=True)
        if a in keep and b in keep
    ]
    return nodes, edges


async def _from_library(
    database_url: str, site: str, out_links: list[str]
) -> tuple[list[str], dict[str, list[str]], dict[str, tuple[bool, bool]]]:
    """Who links to the site, the links among the neighbours, and what is known about each."""
    async with await psycopg.AsyncConnection.connect(database_url, connect_timeout=5) as conn:
        cur = await conn.execute(
            """SELECT DISTINCT site FROM pages
               WHERE out_domains @> %s::text[] AND site IS NOT NULL AND site <> %s LIMIT %s""",
            ([site], site, MAX_IN),
        )
        in_links = [r[0] for r in await cur.fetchall()]
        members = list({*out_links[:MAX_OUT], *in_links})
        neighbour_links: dict[str, list[str]] = defaultdict(list)
        library: dict[str, tuple[bool, bool]] = {}
        if members:
            wanted = set(members) | {site}
            cur = await conn.execute(
                """SELECT site, out_domains, label FROM pages WHERE site = ANY(%s) LIMIT 4000""",
                (members,),
            )
            for source, targets, label in await cur.fetchall():
                scam, honest = library.get(source, (False, False))
                library[source] = (scam or label == "phish", honest or label == "benign")
                for target in targets or []:
                    if target in wanted and target not in neighbour_links[source]:
                        neighbour_links[source].append(target)
    return in_links, dict(neighbour_links), library


async def find(database_url: str | None, site: str | None, out_links: list[str]) -> GraphResult:
    if not site:
        return GraphResult(status="skipped", note="The link has no site name to place in a graph.")
    in_links: list[str] = []
    neighbour_links: dict[str, list[str]] = {}
    library: dict[str, tuple[bool, bool]] = {}
    unavailable = False
    if database_url:
        try:
            in_links, neighbour_links, library = await _from_library(database_url, site, out_links)
        except Exception as err:
            log.warning("link graph lookup failed: %s", type(err).__name__)
            unavailable = True
    graph = build(site, out_links, in_links, neighbour_links, library)
    result = judge(site, graph)
    if unavailable and result.status == "no_links":
        result.status = "unavailable"
        result.note = "The page library couldn't be read, so only this page's own links are shown."
    return result
