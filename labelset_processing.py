import networkx as nx
import numpy
from typing import Set, Dict
from utils import tuple_contains


def create_subgraph(graph: nx.DiGraph, root_node, direction='descendants'):
    if direction == 'descendants':
        children = nx.descendants(graph, root_node)
    else:
        children = nx.ancestors(graph, root_node)
    children.add(root_node)
    sg = nx.subgraph(graph, children)
    nx.write_gexf(sg, '/tmp/label_hierarchy_sg.gexf')
    return sg


def find_lowfreq_hubs(g):
    node_anc_weight = []
    for node in g.nodes():
        ancestors = list(nx.ancestors(graph, node))
        if ancestors:
            avg_anc_weights  = numpy.mean([g.nodes()[anc].get('weight', 0) for anc in ancestors])
            if avg_anc_weights > 0:
                node_anc_weight.append((avg_anc_weights, node))
    node_anc_weight.sort()
    breakpoint()


def get_popular_descendants(node, g, descendants=None, min_freq=50):
    if descendants is None:
        descendants = set()
    successors = list(g.successors(node))
    if successors:
        for neighbor in successors:
            if g.nodes()[neighbor].get('weight', 0) >= min_freq or  \
                    g.nodes()[neighbor].get('ancestor support', 0) >= min_freq:
                descendants.add(neighbor)
            else:
                return get_popular_descendants(neighbor, g, descendants=descendants, min_freq=min_freq)
    return descendants


def map_lowfreq_labels(g: nx.DiGraph, min_freq: int = 50) -> Dict[str, Set[str]]:
    label_merges = dict()
    for node in g.nbunch_iter():

        if g.nodes()[node]['real_label'] and \
                g.nodes()[node].get('weight', 0) < min_freq and \
                len(node) > 1:
            scored_neighbors = []
            mapped_labels = set()
            for neighbor in g.successors(node):
                neighbor_weight = g.nodes()[neighbor].get('weight', 0)
                scored_neighbors.append((neighbor_weight, neighbor))
            scored_neighbors.sort(reverse=True)

            for score, neighbor in scored_neighbors:
                if (score >= min_freq or g.nodes()[neighbor].get('ancestor support', 0) >= min_freq): # and g.nodes()[neighbor]['real_label']:  # Allow synthetic labels?
                    mapped_labels.add(neighbor)
                else:
                    # Decompose further
                    descendants = get_popular_descendants(neighbor, g)
                    mapped_labels.update(descendants)

            label_merges[node] = mapped_labels
    return label_merges


def decompose_to_roots(g: nx.DiGraph, min_freq: int = 50) -> Dict[str, Set[str]]:
    label2roots = dict()
    roots = [n for n in graph.nbunch_iter() if not list(graph.successors(n))
             and list(graph.predecessors(n))
             and (g.nodes()[n].get('weight', 0) >= min_freq or g.nodes()[n].get('ancestor support', 0) >= min_freq)]
    real_roots = [n for n in graph.nbunch_iter() if not list(graph.successors(n))
                  and list(graph.predecessors(n)) and graph.nodes()[n]['real_label']
                  and g.nodes()[n].get('weight', 0) >= min_freq]
    for node in g:
        if len(node) > 1:
            if g.nodes()[node]['real_label']:
                descendants = nx.descendants(g, node)
                if descendants:
                    real_root_labels = {l for l in descendants if l in real_roots}
                    root_labels = {l for l in descendants if l in roots}
                else:
                    root_labels, real_root_labels = {node}, {node}
                print(node)
                print(real_root_labels)
                print(root_labels)
                breakpoint()

    return label2roots


def decompose_real_labels_to_roots(g: nx.DiGraph, min_freq: int = 50) -> Dict[str, Set[str]]:
    label2roots = dict()
    real_roots = [n for n in graph.nbunch_iter() if not list(graph.successors(n))
                  and list(graph.predecessors(n)) and g.nodes()[n].get('weight', 0) >= min_freq]
    for node in g:
        if len(node) > 1:
            descendants = nx.descendants(g, node)
            if descendants:
                real_root_labels = {l for l in descendants if l in real_roots}
            else:
                real_root_labels = {node}
            print(node)
            print(real_root_labels)
            breakpoint()
    return label2roots


def calc_token_association(graph):
    from collections import Counter
    from labelset_hierarchy import get_ngrams
    from nltk.corpus import stopwords
    stop_words = set(stopwords.words('english'))
    ngram_counts = Counter()

    for node in graph.nodes():
        for ngram in get_ngrams(node):
            if ngram == node:
                ngram_counts[ngram] += 1
            else:
                # Filter ngrams that consist of stopwords only, or those that have stop words at borders
                filtered = [l for l in ngram if l not in stop_words]
                if filtered:
                    if not ngram[-1] in stop_words and not ngram[0] in stop_words:
                        ngram_counts[ngram] += 1

    jaccard_indexes = dict()
    for ngram, cnt in ngram_counts.items():
        if len(ngram) > 1:
            nouns = [l for l in ngram if l not in stop_words]
            if nouns:
                delim = sum(ngram_counts[tuple([noun])] for noun in nouns)
                if delim == 0:
                    jaccard_indexes[ngram] = 0
                else:
                    jacc_ix = cnt / delim
                    jaccard_indexes[ngram] = jacc_ix

    return jaccard_indexes


def find_strong_token_coocurrence(g: nx.DiGraph):
    for node in g.nodes():
        for predecessor in g.predecessors(node):
            if g.nodes()[predecessor].get('weight', 0) > g.nodes()[node]['weight']:
                print(node, predecessor)
                breakpoint()


def prune_sparse_roots(g: nx.DiGraph, min_freq: int = 50) -> nx.DiGraph:
    spare_roots = [n for n in g.nodes() if not list(g.successors(n)) and g.nodes()[n]['weight'] < min_freq]
    g.remove_nodes_from(spare_roots)
    return g


if __name__ == '__main__':
    corpus_file = 'sec_corpus_2016-2019_clean.jsonl'
    graph_file = corpus_file.replace('.jsonl', '_real_label_hierarchy.gexf')
    print('Reading graph from', graph_file)
    graph = nx.read_gexf(graph_file)

    # Convert node names from strings back to tuples:
    name_map = {l: eval(l) for l in graph.nodes()}
    graph = nx.relabel_nodes(graph, name_map)

    graph = prune_sparse_roots(graph)

    # find_strong_token_coocurrence(graph)

    # Decompose into (real) roots
    label2roots = decompose_real_labels_to_roots(graph)

    # find association between tokens to identify non-splitable labels
    token_assoc = calc_token_association(graph)


    roots = [n for n in graph.nbunch_iter() if not list(graph.successors(n))
             and list(graph.predecessors(n))]
    real_roots = [n for n in graph.nbunch_iter() if not list(graph.successors(n))
                  and list(graph.predecessors(n)) and graph.nodes()[n]['real_label']]

    jacc_ixs = calc_token_association(graph)

    # Split labels into parents with sufficient support
    label_merges = map_lowfreq_labels(graph, min_freq=100)
    breakpoint()
    # non_merged_labels = [n for n in graph.nbunch_iter() if n not in label_merges]

    # find nodes where the average weight of the ancestors is low
    find_lowfreq_hubs(graph)

    """
    interesting:
('termination', 'by', 'tyson', 'without', 'cause', 'or', 'by', 'you', 'for', 'good', 'reason')
[(122, "('good', 'reason')"), (9, "('termination', 'by', 'tyson', 'without', 'cause')")]
print(list(g.successors("('termination', 'by', 'tyson', 'without', 'cause')")))
["('termination',)", "('without', 'cause')"]
-> 'by tyson' gets croped out, exactly as we want!
-> interesting: we have a node ('termination', 'without', 'cause');
i.e. we could check if a target has a common ancestors/if the concatenation of the labels is a (true) label! if yes, take that as the merge target!
     """

    # TODO check for node labels that consist of token with strong association
    #  (i.e. "change of control"; "governing law")
