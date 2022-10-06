import logging
import os
import ssl

from copy import deepcopy
from datetime import datetime
from feedparser import parse as parse_rss_feeds
from time import sleep

from sgsuite.util import archiveNowProxy
from sgsuite.util import expandUrl
from sgsuite.util import genericErrorInfo
from sgsuite.util import getDedupKeyForURI
from sgsuite.util import getDomain

logger = logging.getLogger('sgsuite.sgsuite')
if hasattr(ssl, '_create_unverified_context'): ssl._create_default_https_context = ssl._create_unverified_context

def get_memento_rss_feed(uri):

    uri = uri.strip()
    if( uri == '' ):
        return '', {}

    rss_feed = {}
    id_rss_memento = ''
    rss_memento = archiveNowProxy(uri)
    
    indx = rss_memento.rfind('/http')
    if( indx != -1 ):
        id_rss_memento = rss_memento[:indx] + 'id_' + rss_memento[indx:]

    if( id_rss_memento != '' ):
        try:
            rss_feed = parse_rss_feeds(id_rss_memento)
        except:
            genericErrorInfo()

    return id_rss_memento, rss_feed

def get_lnks_frm_feeds(uri, link_count=1, archive_rss_flag=True, rss_fields=['title', 'published', 'published_parsed'], expand_url=False):

    '''
        For news sources with rss links, get link_count links from uri

        param uri: rss link for source to dereference
        param link_count: the number of news links to extract for uri

        links format:
        [
            {
                link: val,
                title: val,
                published: val
            },
        ]
    '''

    if( expand_url is True ):
        uri = expandUrl(uri)
        uri = uri.strip()

    if( uri == '' ):
        return [], {}

    links = []
    
    logger.info('get_lnks_frm_feeds(), link_count: ' + str(link_count))
    logger.info('\turi: '+ uri)

    #attempt to process memento of rss - start
    if( archive_rss_flag is True ):
        id_rss_memento, rss_feed = get_memento_rss_feed(uri)
    else:
        logger.info('\tarchive_rss_flag False')
        id_rss_memento = ''
        rss_feed = {}
    #attempt to process memento of rss - end


    if( len(rss_feed) == 0 ):
        logger.info('\trss: use uri-r')
        #here means that for some reason it was not possible to process rss memento, so use live version
        try:
            rss_feed = parse_rss_feeds(uri)
        except:
            genericErrorInfo()
    else:
        logger.info('\trss: use uri-m: ' + id_rss_memento)


    for i in range(len(rss_feed.entries)):
        
        entry = rss_feed.entries[i]
        try:

            if( 'link' not in entry ):
                continue

            temp_dct = {}
            temp_dct['link'] = expandUrl(entry.link)    
            temp_dct['rss-uri-m'] = id_rss_memento
            
            for field in rss_fields:
                if( field in entry ):
                    temp_dct[field] = entry[field]
                else:
                    temp_dct[field] = None


            links.append( temp_dct )
        except:
            genericErrorInfo()

        if( i+1 == link_count ):
            break

    return links, rss_feed

'''
    rss_links: {
        'rss': ''
        'custom': {}
    }
'''
def get_news_articles_frm_rss(rss_links, max_lnks_per_src=1, archive_rss_flag=False, rss_fields=['title', 'published'], expand_url=False, **kwargs):

    if( len(rss_links) == 0 or max_lnks_per_src < 1 ):
        return {}, {}

    '''
        news_articles format:
        {
            domain_x: {link: link, ...},
            domain_y-0: {link: link, ...},
            domain_y-1: {link: link, ...}
        }
    '''

    dedup_set = set()
    news_articles = {}
    news_article_counts = {}
    articles_to_rename = {}
    domain_rss_feeds = {}
    throttle = 0

    for rss_dets in rss_links:

        if( throttle > 0 and archive_rss_flag is True ):
            logger.info('\n\tget_news_articles_frm_rss(): throttle IA, sleep: ' + str(throttle))
            sleep(throttle)

        prev_now = datetime.now()        
        links, rss_feed = get_lnks_frm_feeds( rss_dets['rss'].strip(), max_lnks_per_src, archive_rss_flag=archive_rss_flag, rss_fields=rss_fields, expand_url=expand_url )
        
        for uri_dets in links:
            
            uri_dets['link'] = uri_dets['link'].strip()
            domain = getDomain(uri_dets['link'], includeSubdomain=True)

            if( domain == '' ):
                continue

            uri_dedup_key = getDedupKeyForURI( uri_dets['link'] )
            if( uri_dedup_key in dedup_set ):
                continue


            dedup_set.add( uri_dedup_key )
            
            domain_rss_feeds.setdefault(domain, rss_feed)
            news_article_counts.setdefault(domain, -1)
            news_article_counts[domain] += 1


            #news_article_counts[domain] is count of domain instances already seen
            domain_or_domain_count_key = ''
            if( news_article_counts[domain] == 0 ):
                domain_or_domain_count_key = domain
            else:
                domain_or_domain_count_key = domain + '-' + str( news_article_counts[domain] )
                articles_to_rename[domain] = True


            temp_dct = {}
            for key, value in uri_dets.items():
                temp_dct[key] = value
            #transfer custom properties from rss - start
            if( 'custom' in rss_dets ):
                for key, value in rss_dets['custom'].items():
                    if( isinstance(value, dict) ):
                        temp_dct[key] = deepcopy(value)
                    else:   
                        temp_dct[key] = value
            #transfer custom properties from rss - end

            news_articles[ domain_or_domain_count_key ] = temp_dct
            #news_articles[ domain_or_domain_count_key ] = {'link': uri, 'title': uri_dets['title'], 'published': uri_dets['published'], 'label': rss_dets['label']}
        
        delta = datetime.now() - prev_now
        if( delta.seconds < 1 ):
            throttle = 1


    #rename first instance of source with multiple instance as source-0 - start
    for domain in articles_to_rename:
        news_articles[domain + '-0'] = news_articles.pop(domain)
    #rename first instance of source with multiple instance as source-0 - end

    return news_articles, domain_rss_feeds
