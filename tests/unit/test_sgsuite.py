import logging
import unittest

from sgsuite.ClusterNews import ClusterNews
from sgsuite.util import dumpJsonToFile

class TestSGTK(unittest.TestCase):

    logging.basicConfig(format='', level=logging.INFO)
    logger = logging.getLogger(__name__)

    def test_get_entities_frm_links(self):

        uris_lst = [
            "https://www.politicususa.com/2018/06/28/trump-walker-foxconn-scam.html",
            "https://www.politicususa.com/2018/06/28/mueller-subpoenas-another-associate-of-trump-adviser-roger-stone.html",
            "https://www.politicususa.com/2018/06/28/adam-schiff-republicans.html"
        ]
        
        sgc = ClusterNews(min_sim=0.3, jaccard_weight=0.3, sim_metric='weighted-jaccard-overlap', graph_name='xgraph_name', graph_description='graph_description')
        sg_nodes = sgc.gen_storygraph(uris_lst)
        dumpJsonToFile('news_clusters_annotated.json', sg_nodes, indentFlag=True)



if __name__ == '__main__':
    unittest.main()