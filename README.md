# StoryGraph Suite 

Storygraph suite provides a collection of software tools currently used by [StoryGraph](http://storygraph.cs.odu.edu/). The current list of tools includes:
1. Utility to parse RSS feeds (based on feedparser)
2. Implementation of StoryGraph's news clustering algorithm

### Installation
Use the following command to install this Python-based suite,
```sh
$ git clone https://github.com/oduwsdl/storygraph-suite.git
$ cd storygraph-suite/
$ pip install .
$ cd ..; rm -rf storygraph-suite;
```
### Usage examples
Consider the following examples using the RSS parser and News clusterer.
#### RSS Parser
The following example illustrates the basic use of the `get_news_articles_frm_rss` to extract 5 (`max_links`) links from `foxnews.com` and `vox.com`, and `politico.com`.
```python
import json
from sgsuite.rss_parser import get_news_articles_frm_rss

feeds = [
    {
        #"custom" field is optional and copied included with news link
        "custom": {"node-details": {"annotation": "polarity", "color": "red"," type": "right"}},
        "rss":"http://feeds.foxnews.com/foxnews/latest"
    },
    {
        "custom": {"node-details": {"annotation": "polarity", "color": "blue", "type": "left"}},
        "rss": "https://www.vox.com/rss/index.xml"
    },
    {
        "rss": "http://www.politico.com/rss/politics.xml"
    }
]

# Maximum number of links to extract per rss feed
max_links = 5

# Do NOT archive news links
archive_rss_flag = False

# Fields to extract from each new link (See for full list)[https://feedparser.readthedocs.io/en/latest/reference.html].
rss_fields=['title', 'published', 'published_parsed', 'summary']

sources, raw_rss_feeds = get_news_articles_frm_rss( feeds, max_lnks_per_src=max_links, archive_rss_flag=archive_rss_flag, rss_fields=rss_fields )
with open('news_plus_rss_feeds.json', 'w') as outfile:
    json.dump({'news_sources': sources, 'raw_rss_feeds': raw_rss_feeds}, outfile)
```
#### News Clusterer
sgsuites's `ClusterNews` can be used to cluster a list of news articles `sample_nodes`.
> It's important to note that it's the `entities` NOT text that is used in the clustering process. Therefore, in order to cluster a list of news articles, you must represent each news article as a list of named entities (e.g., `PERSONS`, `LOCATIONS`, `ORGANIZATIONS`) [extracted from the news articles](https://ws-dl.blogspot.com/2018/03/2018-03-04-installing-stanford-corenlp.html).
`sample_nodes` is a list of dictionaries. Each dictionary in `sample_nodes` represents a new article and contains an `entities` list of dictionary entries, where the `entity`, `entity-class` pairs are stored:
```
Minimum key requirement for sample_nodes (input to sgsuite.ClusterNews()):
[
    #news article 1
    {
        "entities":[
            #entity-1
            {
                "entity": "entity",
                "class": "entity-class"
            },...
        ]
    },
    ...
]
```

The following example below illustrates how to cluster (produce `links`) a list of news articles (`sample_nodes`) represented by their respective entities as described by our [CJ2020 publication](https://arxiv.org/abs/2003.09989):
```
from sgsuite.util import derefURI
from sgsuite.util import dumpJsonToFile
from sgsuite.util import getDictFromJson

from sgsuite.ClusterNews import ClusterNews

sample_nodes = 'http://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/2019/11/17/graph115.json'
sample_nodes = getDictFromJson( derefURI(sample_nodes) )

#remove all keys except "nodes"
sample_nodes = sample_nodes['nodes']

min_sim = 0.3#similarity threshold: 1 means 100% match
jaccard_weight = 0.3
sim_metric = "weighted-jaccard-overlap"# others include "jaccard", and "overlap"

graph_stories = ClusterNews( sample_nodes, sim_metric=sim_metric, min_sim=min_sim, jaccard_weight=jaccard_weight )
sample_nodes = graph_stories.cluster_news()

dumpJsonToFile('cluster_news.json', sample_nodes, indentFlag=False)
```

The `cluster_news.json` includes a `links` key, the result of clustering news sources. The annotated version of this file (`cluster_news_annotate.json`) can be visualized ([by uploading the file](http://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/#cursor=93&hist=1440&t=2020-11-28T15:33:50)) if passed to StoryGraph's news annotator: 
```
from sgsuite.util import derefURI
from sgsuite.util import dumpJsonToFile
from sgsuite.util import getDictFromJson

from sgsuite.ClusterNews import ClusterNews

sample_nodes = 'http://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/2019/11/17/graph115.json'
sample_nodes = getDictFromJson( derefURI(sample_nodes) )

#remove all keys except "nodes"
sample_nodes = sample_nodes['nodes']

min_sim = 0.3#similarity threshold: 1 means 100% match
jaccard_weight = 0.3
sim_metric = "weighted-jaccard-overlap"# others include "jaccard", and "overlap"

#run news clustering algorithm
graph_stories = ClusterNews( sample_nodes, sim_metric=sim_metric, min_sim=min_sim, jaccard_weight=jaccard_weight )
sample_nodes = graph_stories.cluster_news()

min_avg_deg = 3
min_uniq_src_count = 3

#annotate sample_nodes so it can be visualized at: http://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/
sample_nodes = ClusterNews.annotate(sample_nodes, min_avg_deg=3, min_uniq_src_count=min_uniq_src_count)
dumpJsonToFile('cluster_news_annotate.json', sample_nodes, indentFlag=False)
```