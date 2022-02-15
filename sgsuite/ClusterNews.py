import itertools
import logging
import networkx as nx

from datetime import datetime
from re import split

from sgsuite.util import genericErrorInfo
from sgsuite.util import getDomain
from sgsuite.util import get_entities_frm_links


logger = logging.getLogger('sgsuite.sgsuite')
class ClusterNews(object):

    def __init__(self, min_sim=0.3, jaccard_weight=0.3, sim_metric='weighted-jaccard-overlap', graph_name='graph_name', graph_description='graph_description', **kwargs):
        
        '''
            entity_dict format:
            {
                'entity': ent,
                'class': class
            }

            nodes_lst format:
            {
                "nodes":
                [
                    {
                        ..."entities": [{entity_dict}]
                    },
                    {
                        ..."entities": [{entity_dict}]
                    },
                    ...
                ]
            }
        '''
        kwargs.setdefault('annotate_min_avg_deg', 3)
        kwargs.setdefault('annotate_min_uniq_src_count', 3)
        
        self.min_sim = min_sim
        self.jaccard_weight = jaccard_weight
        self.sim_metric = sim_metric
        self.graph_name = graph_name
        self.graph_description = graph_description
        self.kwargs = kwargs

        self.entity_extraction_key = 'entity'
        self.entity_container_key = 'entities'
    
    def gen_storygraph(self, links):

        sg = get_entities_frm_links(links)

        #run news clustering algorithm
        #min_sim, similarity threshold: 1 means 100% match
        #sim_metric, #"weighted-jaccard-overlap", "jaccard", and "overlap"
        sg = self.cluster_news(sg)

        #annotate sg_nodes so it can be visualized at: http://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/
        sg = ClusterNews.annotate(sg, min_avg_deg=self.kwargs['annotate_min_avg_deg'], min_uniq_src_count=self.kwargs['annotate_min_uniq_src_count'], graph_name=self.graph_name, graph_description=self.graph_description)

        return sg

    def cluster_news(self, nodes_lst):
        
        logger.info('\ncluster_news():')
        '''
            get all pair keys
            calculate similarity of pair keys
            link pairs within minimum similarity 
        '''
        logger.info('\tsimilarity-metric: ' + self.sim_metric)
        logger.info('\tmin_sim: ' + str(self.min_sim))

        indices = list( range( len(nodes_lst) ) )      
        pairs = list( itertools.combinations(indices, 2) )

        links = []

        for pair in pairs:
            
            first_story = pair[0]
            second_story = pair[1]
            
            sim = self.calc_ent_sim(nodes_lst, first_story, second_story)
            
            if( sim >= self.min_sim ):
                
                lnk_dct = {}
                lnk_dct['source'] = first_story
                lnk_dct['target'] = second_story
                lnk_dct['sim'] = sim
                lnk_dct['rank'] = -1
                links.append(lnk_dct)
                
                logger.info('\tpairs: ' + str(first_story) + ' vs ' + str(second_story))
                logger.info('\t\tsim: ' + str(sim))

                if( 'title' in nodes_lst[first_story] and 'title' in nodes_lst[second_story] ):
                    logger.info('\t\t' + nodes_lst[first_story]['title'][:50] )
                    logger.info('\t\t' + nodes_lst[second_story]['title'][:50] )
                
                logger.info('')

        #add ranks to links - start
        links = sorted( links, key=lambda lnk_dct: lnk_dct['sim'], reverse=True )
        for i in range(0, len(links)):
            links[i]['rank'] = i+1
        #add ranks to links - end

        logger.info( 'pairs count: ' + str(len(pairs)) )

        return {
            'links': links, 
            'nodes': nodes_lst,
            'connected-comps': [],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'custom': {'description': self.graph_description, 'name': self.graph_name}
        }

    def calc_ent_sim(self, nodes_lst, first_story, second_story):

        if( self.entity_container_key not in nodes_lst[first_story] or self.entity_container_key not in nodes_lst[second_story] ):
            return 0
        
        sim = 0    
        first_clust = nodes_lst[first_story][self.entity_container_key]
        second_cluster = nodes_lst[second_story][self.entity_container_key]
        
        firstSet = ClusterNews.get_set_frm_cluster(first_clust, self.entity_extraction_key)
        secondSet = ClusterNews.get_set_frm_cluster(second_cluster, self.entity_extraction_key)

        if( self.sim_metric == 'overlap' ):
            sim = ClusterNews.overlap_set_pair(firstSet, secondSet)

        elif( self.sim_metric == 'jaccard' ):
            sim = ClusterNews.jaccard_set_pair(firstSet, secondSet)

        elif( self.sim_metric == 'weighted-jaccard-overlap' ):
            sim = ClusterNews.weighted_jaccard_overlap_sim( firstSet, secondSet, jaccard_weight=self.jaccard_weight )
        
        else:
            logger.warning('\tClusterNews.calc_single_sim(), no similarity metric: ' + self.sim_metric + ' found, similarity set to minimum (0), try: "weighted-jaccard-overlap", "jaccard", or "overlap"')

        return sim

    @staticmethod
    def jaccard_set_pair(first_set, second_set):

        intersection = float(len(first_set & second_set))
        union = len(first_set | second_set)

        if( union != 0 ):
            return intersection/union
        else:
            return 0

    @staticmethod
    def overlap_set_pair(first_set, second_set):

        intersection = float(len(first_set & second_set))
        minimum = min(len(first_set), len(second_set))

        if( minimum != 0 ):
            return intersection/minimum
        else:
            return 0

    @staticmethod
    def weighted_jaccard_overlap_sim(first_set, second_set, jaccard_weight):

        if( jaccard_weight > 1 ):
            jaccard_weight = 1
        elif( jaccard_weight < 0 ):
            jaccard_weight = 0

        overlap_weight = 1 - jaccard_weight

        jaccard_weight = jaccard_weight * ClusterNews.jaccard_set_pair(first_set, second_set)
        overlap_weight = overlap_weight * ClusterNews.overlap_set_pair(first_set, second_set)

        return jaccard_weight + overlap_weight

    @staticmethod
    def unused_word_tokenizer(txt, split_pattern="[^a-zA-Z0-9.'’]"):
        txt = txt.replace('\n', ' ')
        return split(split_pattern, txt)

    @staticmethod
    def get_set_frm_cluster(cluster, extraction_key):

        ent_set = set()

        for set_member in cluster:
            
            if( 'class' not in set_member or extraction_key not in set_member ):
                continue

            if( set_member['class'].upper() in ['DATE', 'PERCENT', 'MONEY'] ):
                #don't tokenize datetimes and percent and money
                ent_set.add( set_member[extraction_key].lower() )
            else:
                ent_toks = set_member[extraction_key].lower().split(' ')
                for sing_tok in ent_toks:
                    
                    sing_tok = sing_tok.strip()
                    if( sing_tok != '' ):
                        ent_set.add( sing_tok )

        return ent_set

    #annotate news graph - start

    @staticmethod
    def connected_component_subgraphs(G):
        
        all_cc = []
        for c in nx.connected_components(G):
            all_cc.append( G.subgraph(c) )

        return all_cc

    @staticmethod
    def get_avg_degree(G):
    
        nnodes= G.number_of_nodes()
        s = sum( [val for (node, val) in G.degree()] )

        if( nnodes == 0 ):
            return 0

        return s/float(nnodes)

    @staticmethod
    def news_event_annotate(annotation_name, story_graph, min_avg_deg, min_uniq_src_count, **kwargs):

        if( 'links' not in story_graph or 'nodes' not in story_graph ):
            return story_graph

        '''
            precondition for unique src count:
            "link" in story_graph['nodes']
        '''
        
        #reset state - start
        domain_count = {}
        for i in range(0, len(story_graph['nodes'])):

            node = story_graph['nodes'][i]
            if( 'link' not in node or 'id' in node ):
                continue
            
            node.setdefault('node-details', {})
            node['node-details'].setdefault('annotation', annotation_name)
            node['node-details']['connected-comp-type'] = ''

            domain = getDomain( node['link'] )
            domain_count.setdefault( domain, -1 )
            domain_count[domain] += 1
            node['id'] = domain + '-' + str(domain_count[domain])
        #reset state - end  

        if( len(story_graph['links']) == 0 ):
            return story_graph

        G = nx.Graph()
        for edge in story_graph['links']:
            G.add_edge(edge['source'], edge['target'])
        
        story_graph['connected-comps'] = []
        subgraphs = ClusterNews.connected_component_subgraphs(G)

        for subgraph in subgraphs:
            
            avg_deg = ClusterNews.get_avg_degree(subgraph)
            nodes = list( subgraph.nodes() )
            unique_src_count = {}

            for story_idx in nodes:
                if( 'id' not in story_graph['nodes'][story_idx] ):
                    continue
                source = story_graph['nodes'][story_idx]['id'].split('-')[0]
                unique_src_count[source] = True

            conn_comp_type = {}
            conn_comp_type['annotation'] = annotation_name
            if( avg_deg >= min_avg_deg and len(unique_src_count) >= min_uniq_src_count ):
                conn_comp_type['connected-comp-type'] = 'event'
                conn_comp_type['color'] = 'green'
            else:
                conn_comp_type['connected-comp-type'] = 'cluster'
                conn_comp_type['color'] = 'red'

            conn_comp_dets = {}
            conn_comp_dets['nodes'] = nodes
            conn_comp_dets['node-details'] = conn_comp_type
            conn_comp_dets['avg-degree'] = avg_deg
            conn_comp_dets['density'] = nx.density(subgraph)
            conn_comp_dets['unique-source-count'] = len(unique_src_count)

            for story_idx in nodes:
                if( 'color' not in story_graph['nodes'][story_idx]['node-details'] ):
                    story_graph['nodes'][story_idx]['node-details']['color'] = conn_comp_type['color']
                story_graph['nodes'][story_idx]['node-details']['connected-comp-type'] = conn_comp_type['connected-comp-type']

            story_graph['connected-comps'].append(conn_comp_dets)

        return story_graph

    @staticmethod
    def annotate(story_graph, min_avg_deg, min_uniq_src_count, annotation_name='event-cluster', **kwargs):
        
        if( annotation_name == 'event-cluster' ):
            story_graph = ClusterNews.news_event_annotate(annotation_name, story_graph, min_avg_deg, min_uniq_src_count, **kwargs)

        return story_graph
        
    #annotate news graph - end
