# StoryGraph Suite 

StoryGraph suite provides a collection of software tools currently used by [StoryGraph](http://storygraph.cs.odu.edu/):
1. [Text processing pipeline](#text-processing-pipeline) (Command line & Python function): Dereference URI -> Boilerplate removal -> [Named Entity Extraction](https://spacy.io/usage/linguistic-features#named-entities) 
2. [Run StoryGraph's news clustering algorithm](generate-news-similarity-graph) (Command line & Python function)
3. [Utility to parse RSS feeds (based on feedparser)](rss-Parser)

### Installation
Use the following command to install this Python-based suite,
```sh
$ git clone https://github.com/oduwsdl/storygraph-suite.git
$ pip install storygraph-suite/
$ rm -rf storygraph-suite
```
### Usage examples
Consider the following command-line/Python script usage examples
#### Text Processing Pipeline
Command-line usage syntax:
```
Usage: $ sgs [options] input
input: single or multiple URLs and/or text files (1 URL per line) and/or JSON files (1 JSON record per line with MANDATORY "link" key)
```
For example, dereference, remove boilerplate, and extract entities from 5 URIs from 3 sources:
* Command line
* Text file: `t.txt` with 1 URI per line
* JSON file: `j.json` with 1 JSON record per line with mandaory `"link"` key
```
$ sgs --no-storygraph -o links.jsonl.txt https://www.politicususa.com/2019/03/24/democrats-barr-testify.html https://www.breitbart.com/politics/2019/03/24/report-mueller-probe-concludes-trump-didnt-commit-crime/ t.txt j.json

Content of t.txt:
https://www.vox.com/policy-and-politics/2019/3/24/18279876/mueller-report-barr-trump-political-victory

Content of j.json:
{"link": "https://www.breitbart.com/politics/2019/03/24/graham-mueller-report-great-job-special-counsel-great-day-president-trump/", "property_0": 0}
{"link": "https://www.washingtonexaminer.com/news/i-was-wrong-bloomberg-apologizes-for-stop-and-frisk", "property_0": 1}
```
The output (1 line per link) is written to a `links.jsonl.txt` with the following content:
```
content of links.jsonl.txt:
{"link": "https://www.politicususa.com/2019/03/24/democrats-barr-testify.html", "title": "...", "text": "...", "favicon": "...", "entities": []}
...
```
The same results can be also be achieved from a Python script:
```python
from sgsuite.util import parse_inpt_for_links
from sgsuite.util import get_entities_frm_links

all_link_details = parse_inpt_for_links(['https://www.politicususa.com/2019/03/24/democrats-barr-testify.html', 'https://www.breitbart.com/politics/2019/03/24/report-mueller-probe-concludes-trump-didnt-commit-crime/', 't.txt', 'j.json'])
links_only = [l['link'] for l in all_link_details]

#links contains content similar to links.jsonl.txt above
links = get_entities_frm_links(links_only)
```
#### Generate news similarity graph
Run StoryGraph's news similarity graph algorithm (See [CJ2020 publication](https://arxiv.org/abs/2003.09989)) from the command line with the same input/files from the [text processing pipeline example](#text-processing-pipeline) by excluding the `--no-storygraph` option:
```
$ sgs -o news_sim_graph.json https://www.politicususa.com/2019/03/24/democrats-barr-testify.html https://www.breitbart.com/politics/2019/03/24/report-mueller-probe-concludes-trump-didnt-commit-crime/ t.txt j.json
```
`news_sim_graph.json` is structured similarly to StoryGraph's [files](https://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/2019/11/17/graph115.json), and as such, can be visualized by [uploading](https://storygraph.cs.odu.edu/graphs/polar-media-consensus-graph/#cursor=98&hist=1440&t=2019-03-21T16:26:25) (Click browse button at the bottom right).

A similar result can be achieved from a Python script via `ClusterNews(min_sim=0.3, jaccard_weight=0.3, sim_metric='weighted-jaccard-overlap', graph_name='graph_name', graph_description='graph_description', **kwargs)`:

```python
import json
from sgsuite.ClusterNews import ClusterNews
from sgsuite.util import parse_inpt_for_links

all_link_details = parse_inpt_for_links(['https://www.politicususa.com/2019/03/24/democrats-barr-testify.html', 'https://www.breitbart.com/politics/2019/03/24/report-mueller-probe-concludes-trump-didnt-commit-crime/', 't.txt', 'j.json'])
only_links = [l['link'] for l in all_link_details]

sgc = ClusterNews(graph_name='SGTestGraph', graph_description="Testing StoryGraph's news clustering algorithm")
sg_graph = sgc.gen_storygraph(only_links)

with open('news_sim_graph.json', 'w') as outfile:
    json.dump(sg_graph, outfile, ensure_ascii=False)
```
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
    json.dump({'news_sources': sources, 'raw_rss_feeds': raw_rss_feeds}, outfile, ensure_ascii=False)
```