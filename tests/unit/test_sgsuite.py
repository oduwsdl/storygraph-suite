import logging
import unittest

from sgsuite.ClusterNews import ClusterNews
from sgsuite.util import dumpJsonToFile

class TestSGSuite(unittest.TestCase):

    logging.basicConfig(format='', level=logging.INFO)
    logger = logging.getLogger(__name__)

    def test_cluster_news(self):

        uris_lst = [
            "https://en.wikipedia.org/wiki/Norfolk",
            "https://en.wikipedia.org/wiki/Norfolk",
            "https://en.wikipedia.org/wiki/Norfolk"
        ]
        
        sgc = ClusterNews(min_sim=0.3, jaccard_weight=0.3, sim_metric='weighted-jaccard-overlap', graph_name='xgraph_name', graph_description='graph_description')
        sg_nodes = sgc.gen_storygraph(uris_lst)
        self.assertGreater( len(sg_nodes['links']), 0, 'links.len == 0' )

if __name__ == '__main__':
    unittest.main()