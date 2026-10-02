"""Link-graph inference (SiNMULI). Small hand-made graphs with reserved example names."""

import networkx as nx
import pytest

from app import graph as g
from app.analysis import analyze
from app.analysis.score import graph_reasons

pytestmark = [pytest.mark.anyio, pytest.mark.real_library]

ME = "new-site.example.com"
# What the page library knows: (has scam pages, has honest pages).
LIBRARY = {
    "honest-a.example.org": (False, True),
    "honest-b.example.org": (False, True),
    "honest-c.example.org": (False, True),
    "scam-a.example.net": (True, False),
    "scam-b.example.net": (True, False),
    "mixed.example.net": (True, True),
}


def test_starting_signs_follow_the_paper():
    assert g.edge_sign(1, 1) == 1  # honest -> honest
    assert g.edge_sign(1, -1) == -1  # anything involving a known scam
    assert g.edge_sign(-1, 1) == -1
    assert g.edge_sign(0, 1) == 0  # from an unknown site: unknown
    assert g.edge_sign(1, 0) == 1


def test_site_labels_need_clear_evidence():
    assert g.site_label("honest-a.example.org", LIBRARY) == (1, "known honest pages")
    assert g.site_label("scam-a.example.net", LIBRARY) == (-1, "known scam pages")
    assert g.site_label("mixed.example.net", LIBRARY) == (0, None)  # both kinds of pages: unknown
    assert g.site_label("never-seen.example.com", LIBRARY) == (0, None)


def test_the_51_percent_rule_abstains_on_ties():
    assert g.majority_label(3, 1) == 1
    assert g.majority_label(1, 3) == -1
    assert g.majority_label(2, 2) == 0
    assert g.majority_label(0, 0) == 0
    assert g.majority_label(51, 49) == 0  # 51% exactly is not "more than 51%"
    assert g.majority_label(52, 48) == 1


def test_balance_fills_in_the_one_unknown_edge_of_a_triangle():
    # i -> j, j -> k, i -> k with j unlabeled: s(j,k) = s(i,j) * s(i,k).
    graph = nx.DiGraph()
    graph.add_node("i", label=1)
    graph.add_node("j", label=0)
    graph.add_node("k", label=-1)
    graph.add_edge("i", "j", sign=1, inferred=False)
    graph.add_edge("i", "k", sign=-1, inferred=False)
    graph.add_edge("j", "k", sign=0, inferred=False)
    used, inferred = g.infer_signs(graph)
    assert (used, inferred) == (1, 1)
    assert graph.edges["j", "k"]["sign"] == -1 and graph.edges["j", "k"]["inferred"] is True


def test_triangles_with_two_unknowns_are_left_alone():
    graph = nx.DiGraph()
    for name, label in (("i", 0), ("j", 0), ("k", 1)):
        graph.add_node(name, label=label)
    graph.add_edge("i", "j", sign=0, inferred=False)
    graph.add_edge("j", "k", sign=0, inferred=False)
    graph.add_edge("i", "k", sign=0, inferred=False)
    assert g.infer_signs(graph) == (0, 0)


def test_a_site_linked_from_scam_sites_is_called_malicious():
    built = g.build(
        ME,
        out_links=["scam-a.example.net", "honest-a.example.org"],
        in_links=["scam-a.example.net", "scam-b.example.net", "honest-a.example.org"],
        neighbour_links={"honest-a.example.org": ["scam-a.example.net"]},
        library=LIBRARY,
    )
    got = g.judge(ME, built)
    assert got.status == "labelled" and got.label == "malicious"
    assert (got.positive_in, got.negative_in) == (1, 2)
    assert got.scam_links_out == 1 and got.links_out == 2
    assert got.note.startswith("2 of 3 known sites that link here are scam sites.")
    assert "links to 1 known scam site" in got.note
    # honest-a -> me (+1), honest-a -> scam-a (-1), me -> scam-a (unknown): balance makes it -1.
    edge = next(e for e in got.edges if e.source == ME and e.target == "scam-a.example.net")
    assert edge.sign == -1 and edge.inferred is True
    assert got.triads >= 1 and got.inferred_edges >= 1
    assert got.nodes[0].id == ME and got.nodes[0].role == "scanned" and got.nodes[0].label == 0
    roles = {n.id: n.role for n in got.nodes}
    assert roles["scam-a.example.net"] == "both" and roles["scam-b.example.net"] == "linked_from"


def test_a_site_linked_from_honest_sites_is_called_benign():
    in_links = ["honest-a.example.org", "honest-b.example.org", "honest-c.example.org"]
    got = g.judge(ME, g.build(ME, [], in_links, {}, LIBRARY))
    assert got.label == "benign" and got.positive_in == 3
    assert got.note == "3 of 3 known sites that link here are honest sites."


def test_no_known_links_means_no_opinion():
    got = g.judge(ME, g.build(ME, ["never-seen.example.com"], [], {}, LIBRARY))
    assert got.status == "no_links" and got.label is None
    assert "normal for new domains" in got.note
    split = g.judge(ME, g.build(ME, [], ["honest-a.example.org", "scam-a.example.net"], {}, LIBRARY))
    assert split.status == "abstained" and "don't agree" in split.note


async def test_find_without_a_library_still_draws_the_pages_own_links():
    got = await g.find(None, ME, ["a.example.org", "b.example.org"])
    assert got.status == "no_links" and got.links_out == 2
    assert {n.id for n in got.nodes} == {ME, "a.example.org", "b.example.org"}
    assert (await g.find(None, None, [])).status == "skipped"


async def test_find_survives_a_broken_library(monkeypatch):
    async def broken(database_url, site, out_links):
        raise ConnectionError("down")

    monkeypatch.setattr(g, "_from_library", broken)
    got = await g.find("postgresql://x", ME, ["a.example.org"])
    assert got.status == "unavailable" and got.links_out == 1


def test_graph_points():
    def points(**kw):
        return [(r.points, r.area) for r in graph_reasons(kw, trusted=False)[0]]

    assert points(status="labelled", label="malicious", negative_in=3, positive_in=1) == [(20, "graph")]
    assert points(status="labelled", label="malicious", negative_in=1, positive_in=0) == [(10, "graph")]
    assert points(status="no_links", scam_links_out=2) == [(15, "graph")]
    assert points(status="no_links") == []
    risks, good = graph_reasons({"status": "labelled", "label": "benign", "positive_in": 4}, trusted=False)
    assert risks == [] and [(r.points, r.area) for r in good] == [(-10, "graph")]
    assert graph_reasons({"status": "labelled", "label": "malicious", "negative_in": 3}, trusted=True) == (
        [],
        [],
    )
    assert graph_reasons(None, trusted=False) == ([], [])


def test_the_graph_shows_up_in_the_verdict():
    visit = {"final_url": "https://plain.example.com/", "hops": [], "html": "<p>hello there</p>"}
    net = {
        "status": "labelled",
        "label": "malicious",
        "negative_in": 3,
        "positive_in": 0,
        "scam_links_out": 1,
    }
    got = analyze(visit, {}, "https://plain.example.com/", None, None, None, net)
    texts = [r.text for r in got.reasons]
    assert "3 of 3 known sites that link to it are scam sites." in texts
    assert "It links to 1 known scam site." in texts
