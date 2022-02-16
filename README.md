# StoryGraph Suite 

Storygraph suite provides a collection of software tools currently used by [StoryGraph](http://storygraph.cs.odu.edu/):
1. [Text (Command line & Python function) processing pipeline](#text-processing-pipeline): Dereference URI -> Boilerplate removal -> Named Entity Extraction 
2. [Run (Command line & Python function) StoryGraph's news clustering algorithm](generate-news-similarity-graph)
3. [Utility to parse RSS feeds (based on feedparser)](rss-Parser)

### Installation
Use the following command to install this Python-based suite,
```sh
$ git clone https://github.com/oduwsdl/storygraph-suite.git
$ cd storygraph-suite/
$ pip install .
$ cd ..; rm -rf storygraph-suite;
```
### Usage examples
Consider the following command-line/library usage examples
#### Text Processing Pipeline
Dereference, remove boilerplate, and extract entities from 5 URIs from 3 sources:
* Command line: https://en.wikipedia.org/wiki/Norfolk
* Text file: `t.txt` with 1 URI per line
* JSON file: `j.json` with 1 JSON record per line with mandaory `"link"` key
```
$ sgs --no-run-storygraph -o links.jsonl.txt https://en.wikipedia.org/wiki/Norfolk t.txt j.json

Content of t.txt:
https://www.govtech.com/security/to-fight-social-media-disinformation-look-to-the-algorithms

Content of j.json:
{"link": "https://www.washingtonexaminer.com/news/i-was-wrong-bloomberg-apologizes-for-stop-and-frisk", "prop_0": 0}
{"link": "https://thehill.com/homenews/campaign/470840-warren-fully-committed-to-medicare-for-all", "prop_0": 1}
```
The output (1 line per link) is written to a `links.jsonl.txt` with the following content:
```
content of links.jsonl.txt:
{"link": "https://en.wikipedia.org/wiki/Norfolk", "title": "...", "text": "...", "favicon": "...", "entities": []}
...
```
The same results can be also be achieved from a Python script:
```
from sgsuite.util import parse_inpt_for_links

all_link_details = parse_inpt_for_links(['https://en.wikipedia.org/wiki/Norfolk', 't.txt', 'j.json'])
only_links = [l['link'] for l in all_link_details]

#links contains content similar to links.jsonl.txt above
links = get_entities_frm_links(only_links)
```
#### Generate news similarity graph
Run StoryGraph's news similarity graph algorithm (See [CJ2020 publication](https://arxiv.org/abs/2003.09989)) from the command line with the same input/files from the [text processing pipeline example](#text-processing-pipeline):
```
$ sgs -o news_graph.json https://en.wikipedia.org/wiki/Norfolk t.txt j.json
```
`news_graph.json` is structured similarly to StoryGraph's [files](https://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/2019/11/17/graph115.json), and as such, can be visualized by [uploading](https://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/#cursor=98&hist=1440&t=2019-03-21T16:26:25) (Click browse button at the bottom right) 

A similar result can be achieved from a Python script via `ClusterNews(min_sim=0.3, jaccard_weight=0.3, sim_metric='weighted-jaccard-overlap', graph_name='graph_name', graph_description='graph_description', **kwargs)`:

```
from sgsuite.ClusterNews import ClusterNews
from sgsuite.util import parse_inpt_for_links

all_link_details = parse_inpt_for_links(['https://en.wikipedia.org/wiki/Norfolk', 't.txt', 'j.json'])
only_links = [l['link'] for l in all_link_details]

sgc = ClusterNews(graph_name='SGTestGraph', graph_description="Testing StoryGraph's news clustering algorithm")
sg_graph = sgc.gen_storygraph(only_links)
```
The content of `sg_graph` is similar to StoryGraph's [files](https://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/2019/11/17/graph115.json).
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