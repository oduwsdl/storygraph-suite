import itertools
import logging
import networkx as nx

from re import split

from sgsuite.util import genericErrorInfo
from sgsuite.util import getISO8601Timestamp

logger = logging.getLogger('sgsuite.sgsuite')
class ClusterNews(object):

    def __init__(self, nodes_lst, sim_metric='weighted-jaccard-overlap', min_sim=0.3, jaccard_weight=0.3, overlap_weight=0.7, **kwargs):
        
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

        self.nodes_lst = nodes_lst
        self.sim_metric = sim_metric
        self.min_sim = min_sim
        self.jaccard_weight = jaccard_weight
        self.overlap_weight = overlap_weight
        self.kwargs = kwargs

        self.entity_extraction_key = 'entity'
        self.entity_container_key = 'entities'
        self.tokenize_classes = kwargs.get('tokenize_classes', ['PERSON', 'LOCATION', 'ORGANIZATION'])
        self.split_pattern = kwargs.get('word_regex_split_pattern', "[^a-zA-Z0-9.'’]")
        
    def cluster_news(self):
        
        logger.info('\ncluster_news():')
        '''
            get all pair keys
            calculate similarity of pair keys
            link pairs within minimum similarity 
        '''
        logger.info('\tsimilarity-metric: ' + self.sim_metric)
        logger.info('\tmin_sim: ' + str(self.min_sim))

        indices = list( range( len(self.nodes_lst) ) )      
        pairs = list( itertools.combinations(indices, 2) )

        links = []

        for pair in pairs:
            
            first_story = pair[0]
            second_story = pair[1]
            
            sim = self.calc_ent_sim(first_story, second_story)
            
            if( sim >= self.min_sim ):
                
                lnk_dct = {}
                lnk_dct['source'] = first_story
                lnk_dct['target'] = second_story
                lnk_dct['sim'] = sim
                lnk_dct['rank'] = -1
                links.append(lnk_dct)
                
                logger.info('\tpairs: ' + str(first_story) + ' vs ' + str(second_story))
                logger.info('\t\tsim: ' + str(sim))

                if( 'title' in self.nodes_lst[first_story] and 'title' in self.nodes_lst[second_story] ):
                    logger.info('\t\t' + self.nodes_lst[first_story]['title'][:50] )
                    logger.info('\t\t' + self.nodes_lst[second_story]['title'][:50] )
                
                logger.info('')

        #add ranks to links - start
        links = sorted( links, key=lambda lnk_dct: lnk_dct['sim'], reverse=True )
        for i in range(0, len(links)):
            links[i]['rank'] = i+1
        #add ranks to links - end

        logger.info( 'pairs count: ' + str(len(pairs)) )

        return {'nodes': self.nodes_lst, 'links': links}

    def calc_ent_sim(self, first_story, second_story):

        if( self.entity_container_key not in self.nodes_lst[first_story] or self.entity_container_key not in self.nodes_lst[second_story] ):
            return 0
        
        sim = 0    
        first_clust = self.nodes_lst[first_story][self.entity_container_key]
        second_cluster = self.nodes_lst[second_story][self.entity_container_key]
        
        firstSet = ClusterNews.get_set_frm_cluster(first_clust, self.entity_extraction_key, split_pattern=self.split_pattern, tokenize_classes=self.tokenize_classes)
        secondSet = ClusterNews.get_set_frm_cluster(second_cluster, self.entity_extraction_key, split_pattern=self.split_pattern, tokenize_classes=self.tokenize_classes)

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
    def word_tokenizer(txt, split_pattern="[^a-zA-Z0-9.'’]"):
        txt = txt.replace('\n', ' ')
        return split(split_pattern, txt)

    @staticmethod
    def get_set_frm_cluster(cluster, extraction_key, split_pattern="[^a-zA-Z0-9.'’]", tokenize_classes=['PERSON', 'LOCATION', 'ORGANIZATION']):

        ent_set = set()

        for set_member in cluster:
            
            if( 'class' not in set_member or extraction_key not in set_member ):
                continue

            ent_class = set_member['class'].upper()

            if( ent_class not in tokenize_classes ):
                #don't tokenize datetimes and percent and money
                ent_set.add( set_member[extraction_key].lower() )
            else:
                #old:
                #ent_toks = set_member[extraction_key].lower().split(' ')
                
                #new/untested:
                ent_toks = ClusterNews.word_tokenizer( set_member[extraction_key].lower().strip(), split_pattern=split_pattern )

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
    def news_event_annotate(annotation_name, story_graph, min_avg_deg, min_uniq_src_count):

        if( 'links' not in story_graph or 'nodes' not in story_graph ):
            return story_graph

        '''
            precondition for unique src count:
            id key of nodes is of form "domain-count", e.g., "cnn.com-1"
        '''

        #reset state - start
        for i in range(0, len(story_graph['nodes'])):

            story_graph['nodes'][i].setdefault('node-details', {})
            story_graph['nodes'][i]['node-details'].setdefault('annotation', annotation_name)
            story_graph['nodes'][i]['node-details']['connected-comp-type'] = ''
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


        story_graph['timestamp'] = getISO8601Timestamp()
        return story_graph

    @staticmethod
    def annotate(story_graph, min_avg_deg, min_uniq_src_count, annotation_name='event-cluster'):
        
        if( annotation_name == 'event-cluster' ):
            story_graph = ClusterNews.news_event_annotate(annotation_name, story_graph, min_avg_deg, min_uniq_src_count)

        return story_graph
        
    #annotate news graph - end
