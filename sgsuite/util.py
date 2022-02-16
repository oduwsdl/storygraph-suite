import os
import json
import logging
import requests
import re
import spacy
import string
import sys
import warnings

from dateparser import parse as parseDateStr
from datetime import datetime
from multiprocessing import Pool
from subprocess import check_output
from time import sleep
from urllib.parse import urlparse

from boilerpy3 import extractors
from bs4 import BeautifulSoup
from NwalaTextUtils.textutils import parallelTask
from NwalaTextUtils.textutils import parallelGetTxtFrmURIs
from tldextract import extract as extract_tld

logger = logging.getLogger('sgsuite.sgsuite')

try:
    spacy.load('en_core_web_sm')
    '''
    This hack was used since adding 
        'en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.1.0/en_core_web_sm-3.1.0.tar.gz#egg=en_core_web_sm' 
    to setup.py's install_requires made the package not uploadable to pypi: "HTTPError: 400 Client Error: Invalid value for requires_dist. Error: Can't have direct dependency: 'en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.1.0/en_core_web_sm-3.1.0.tar.gz#egg=en_core_web_sm' for url: https://upload.pypi.org/legacy/"
    '''
except OSError:
    print('Downloading en_core_web_sm language model for the spaCy NER tagger (This would be done just once)\n')
    from spacy.cli import download
    download('en_core_web_sm')

def getISO8601Timestamp():
    return datetime.utcnow().isoformat() + 'Z'

def genericErrorInfo(slug=''):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    
    errMsg = fname + ', ' + str(exc_tb.tb_lineno)  + ', ' + str(sys.exc_info())
    logger.error(errMsg + slug)

    return errMsg

def getDictFromFile(filename):

    try:

        if( os.path.exists(filename) == False ):
            return {}

        return getDictFromJson( readTextFromFile(filename) )
    except:
        genericErrorInfo('\tgetDictFromFile(): error filename ' + filename)

    return {}

def getTextFromGZ(path):
    
    try:
        with gzip.open(path, 'rb') as f:
            return f.read().decode('utf-8')
    except:
        genericErrorInfo()

    return ''

def getDictFromJson(jsonStr):

    try:
        return json.loads(jsonStr)
    except:
        genericErrorInfo()

    return {}

def gzipTextFile(path, txt):
    
    try:
        with gzip.open(path, 'wb') as f:
            f.write(txt.encode())
    except:
        genericErrorInfo()

def readTextFromFile(infilename):

    try:
        with open(infilename, 'r') as infile:
            return infile.read()
    except:
        genericErrorInfo( '\n\treadTextFromFile(), error filename: ' + infilename )

    return ''

def dumpJsonToFile(outfilename, dictToWrite, indentFlag=True, extraParams=None):

    if( extraParams is None ):
        extraParams = {}

    extraParams.setdefault('verbose', True)

    try:
        outfile = open(outfilename, 'w')
        
        if( indentFlag ):
            json.dump(dictToWrite, outfile, ensure_ascii=False, indent=4)#by default, ensure_ascii=True, and this will cause  all non-ASCII characters in the output are escaped with \uXXXX sequences, and the result is a str instance consisting of ASCII characters only. Since in python 3 all strings are unicode by default, forcing ascii is unecessary
        else:
            json.dump(dictToWrite, outfile, ensure_ascii=False)

        outfile.close()

        if( extraParams['verbose'] ):
            print('\twriteTextToFile(), wrote:', outfilename)
    except:
        if( extraParams['verbose'] ):
            print('\terror: outfilename:', outfilename)
        
        genericErrorInfo()

#html/url - start

def getCustomHeaderDict():

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connnection': 'keep-alive',
        'Cache-Control':'max-age=0' 
    }

    return headers

def archiveNowProxy(uri, params=None):
    
    uri = uri.strip()
    if( len(uri) == 0 ):
        return ''

    if( params is None ):
        params = {}

    if( 'timeout' not in params ):
        params['timeout'] = 10

    try:
        uri = 'https://web.archive.org/save/' + uri
        headers = getCustomHeaderDict()
        
        # push into the archive
        r = requests.get(uri, timeout=params['timeout'], headers=headers, allow_redirects=True)
        r.raise_for_status()
        # extract the link to the archived copy 
        if (r == None):
            logger.error('\narchiveNowProxy(): Error: No HTTP Location/Content-Location header is returned in the response')
            return ''
            
        if 'Location' in r.headers:
            return r.headers['Location']
        elif 'Content-Location' in r.headers:
            return 'https://web.archive.org' + r.headers['Content-Location']    
        else:
            for r2 in r.history:
                if 'Location' in r2.headers:
                    return r2.headers['Location']
                if 'Content-Location' in r2.headers:
                    return r2.headers['Content-Location']
    except Exception as e:
        logger.error('Error msg: ' + str(e))
    except:
        genericErrorInfo()
    
    return ''

def getDedupKeyForURI(uri):

    uri = uri.strip()
    if( len(uri) == 0 ):
        return ''

    exceptionDomains = ['www.youtube.com']

    try:
        scheme, netloc, path, params, query, fragment = urlparse( uri )
        
        netloc = netloc.strip()
        path = path.strip()
        optionalQuery = ''

        if( len(path) != 0 ):
            if( path[-1] != '/' ):
                path = path + '/'

        if( netloc in exceptionDomains ):
            optionalQuery = query.strip()

        netloc = netloc.replace(':80', '')
        return netloc + path + optionalQuery
    except:
        genericErrorInfo('\tgetDedupKeyForURI() uri: ' + uri)

    return ''

def expandUrl(url, secondTryFlag=True, timeoutInSeconds='10'):

    #http://tmblr.co/ZPYSkm1jl_mGt, http://bit.ly/1OLMlIF
    timeoutInSeconds = str(timeoutInSeconds)
    '''
    Part A: Attempts to unshorten the uri until the last response returns a 200 or 
    Part B: returns the lasts good url if the last response is not a 200.
    '''
    url = url.strip()
    if( len(url) == 0 ):
        return ''
    
    try:
        #Part A: Attempts to unshorten the uri until the last response returns a 200 or 
        output = check_output(['curl', '-s', '-I', '-L', '-m', '10', '-c', 'cookie.txt', url])
        output = output.decode('utf-8')
        output = output.splitlines()
        
        longUrl = ''
        path = ''
        locations = []

        for line in output:
            line = line.strip()
            if( len(line) == 0 ):
                continue

            indexOfLocation = line.lower().find('location:')
            if( indexOfLocation != -1 ):
                #location: is 9
                locations.append(line[indexOfLocation + 9:].strip())

        if( len(locations) != 0 ):
            #traverse location in reverse: account for redirects to path
            #locations example: ['http://www.arsenal.com']
            #locations example: ['http://www.arsenal.com', '/home#splash']
            for url in locations[::-1]:
                
                if( url.strip().lower().find('/') == 0 and len(path) == 0 ):
                    #find path
                    path = url

                if( url.strip().lower().find('http') == 0 and len(longUrl) == 0 ):
                    #find url
                    
                    #ensure url doesn't end with / - start
                    #if( url[-1] == '/' ):
                    #   url = url[:-1]
                    #ensure url doesn't end with / - end

                    #ensure path begins with / - start
                    if( len(path) != 0 ):
                        if( path[0] != '/' ):
                            path = '/' + path
                    #ensure path begins with / - end

                    longUrl = url + path

                    #break since we are looking for the last long unshortened uri with/without a path redirect
                    break
        else:
            longUrl = url




        return longUrl
    except Exception as e:
        #Part B: returns the lasts good url if the last response is not a 200.
        #genericErrorInfo()

        if( secondTryFlag ):
            logger.info('\texpandUrl(): second try: ' + url)
            return expandUrlSecondTry(url)
        else:
            return url

def expandUrlSecondTry(url, curIter=0, maxIter=100):

    '''
    Attempt to get first good location. For defunct urls with previous past
    '''

    url = url.strip()
    if( len(url) == 0 ):
        return ''

    if( maxIter % 10 == 0 ):
        logger.info('\t' + str(maxIter) + ' expandUrlSecondTry(): url - ' + url)

    if( curIter>maxIter ):
        return url


    try:

        # when using find, use outputLowercase
        # when indexing, use output
        
        output = check_output(['curl', '-s', '-I', '-m', '10', url])
        output = output.decode('utf-8')
        
        outputLowercase = output.lower()
        indexOfLocation = outputLowercase.rfind('\nlocation:')

        if( indexOfLocation != -1 ):
            # indexOfLocation + 1: skip initial newline preceding location:
            indexOfNewLineAfterLocation = outputLowercase.find('\n', indexOfLocation + 1)
            redirectUrl = output[indexOfLocation:indexOfNewLineAfterLocation]
            redirectUrl = redirectUrl.split(' ')[1]

            return expandUrlSecondTry(redirectUrl, curIter+1, maxIter)
        else:
            return url

    except:
        logger.error('\terror url: ' + url)
        genericErrorInfo()
    

    return url

def getDomain(url, includeSubdomain=False, excludeWWW=True):

    url = url.strip()
    if( len(url) == 0 ):
        return ''

    if( url.find('http') == -1  ):
        url = 'http://' + url

    domain = ''
    
    try:
        ext = extract_tld(url)
        
        domain = ext.domain.strip()
        subdomain = ext.subdomain.strip()
        suffix = ext.suffix.strip()

        if( len(suffix) != 0 ):
            suffix = '.' + suffix 

        if( len(domain) != 0 ):
            domain = domain + suffix
        
        if( excludeWWW ):
            if( subdomain.find('www') == 0 ):
                if( len(subdomain) > 3 ):
                    subdomain = subdomain[4:]
                else:
                    subdomain = subdomain[3:]


        if( len(subdomain) != 0 ):
            subdomain = subdomain + '.'

        if( includeSubdomain ):
            domain = subdomain + domain
    except:
        genericErrorInfo()
        return ''

    return domain

def isSizeLimitExceed(responseHeaders, sizeRestrict):

    if( 'Content-Length' in responseHeaders ):
        if( int(responseHeaders['Content-Length']) > sizeRestrict ):
            return True

    return False

def downloadSave(response, outfile):
    
    try:
        with open(outfile, 'wb') as dfile:
            for chunk in response.iter_content(chunk_size=1024): 
                # writing one chunk at a time to pdf file 
                if(chunk):
                    dfile.write(chunk) 
    except:
        genericErrorInfo()

def mimicBrowser(uri, getRequestFlag=True, timeout=10, sizeRestrict=-1, addResponseHeader=False, saveFilePath=None, headers={}):
    
    uri = uri.strip()
    if( uri == '' ):
        return ''

    if headers == {}:
        headers = getCustomHeaderDict()

    try:
        response = ''
        reponseText = ''
        if( getRequestFlag is True ):

            if( saveFilePath is None ):
                response = requests.get(uri, headers=headers, timeout=timeout)
            else:
                response = requests.get(uri, headers=headers, timeout=timeout, stream=True)
                
            
            if( sizeRestrict != -1 ):
                if( isSizeLimitExceed(response.headers, sizeRestrict) ):
                    return 'Error: Exceeded size restriction: ' + sizeRestrict

            
            if( saveFilePath is None ):
                reponseText = response.text
            else:
                downloadSave(response, saveFilePath)
                

            if( addResponseHeader is True ):
                return  {'response_header': response.headers, 'text': reponseText}

            return reponseText
        else:
            response = requests.head(uri, headers=headers, timeout=timeout)
            response.headers['status_code'] = response.status_code
            return response.headers
    except:
        genericErrorInfo('\n\tmimicBrowser(), error uri: ' + uri)

        if( getRequestFlag is False ):
            return {}
    
    return ''

'''
    Note size limit set to 4MB
'''
def derefURI(uri, sleepSec=0, timeout=10, sizeRestrict=4000000, headers={}, extraParams=None):
    
    uri = uri.strip()
    if( uri == '' ):
        return ''

    if( extraParams is None ):
        extraParams = {}

    htmlPage = ''
    extraParams.setdefault('html_cache_file', '')

    try:

        if( extraParams['html_cache_file'] != '' ):
            htmlPage = getTextFromGZ( extraParams['html_cache_file'] )

            if( htmlPage != '' ):
                logger.info( '\tderefURI(), cache hit' )
                return htmlPage


        if( sleepSec > 0 ):
            logger.info( '\tderefURI(), sleep: ' + str(sleepSec) )
            sleep(sleepSec)
    
        
        htmlPage = mimicBrowser(uri, sizeRestrict=sizeRestrict, headers=headers, timeout=timeout)

        if( extraParams['html_cache_file'] != '' ):
            gzipTextFile( extraParams['html_cache_file'], htmlPage )
    except:
        genericErrorInfo()
    
    return htmlPage

def extractPageTitleFromHTML(html):

    title = ''
    try:
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')

        if( title is None ):
            title = ''
        else:
            title = title.text.strip()
    except:
        genericErrorInfo()

    return title

def parallelGetTxtFrmURIs(urisLst, threadCount=5, updateRate=10):

    size = len(urisLst)
    if( size == 0 ):
        return []

    docsLst = []
    jobsLst = []
    for i in range(size):

        printMsg = ''

        if( i % updateRate == 0 ):
            printMsg = 'dereferencing uri ' + str(i) + ' of ' + str(size)

        keywords = {
            'uri': urisLst[i],
            'sleepSec': 0
        }

        jobsLst.append( {
            'func': derefURI, 
            'args': keywords, 
            'misc': False, 
            'print': printMsg
        })


    resLst = parallelTask(jobsLst, threadCount=threadCount)
    for res in resLst:
        
        text = cleanHtml( res['output'] )
        
        docsLst.append({
            'text': text,
            'title': extractPageTitleFromHTML( res['output'] ),
            'favicon': extractFavIconFromHTML( res['output'], sourceURL=res['input']['args']['uri'] ),
            'uri': res['input']['args']['uri']
        })

    return docsLst

def cleanHtml(html, method='python-boilerpipe'):
    
    if( len(html) == 0 ):
        return ''

    if( method == 'python-boilerpipe' ):
        try:
            '''
            #requires: https://github.com/slaveofcode/boilerpipe3
            from boilerpipe.extract import Extractor
            extractor = Extractor(extractor='ArticleExtractor', html=html)
            return str(extractor.getText())
            '''

            extractor = extractors.ArticleExtractor()
            return extractor.get_content(html)
        except:
            genericErrorInfo()
    elif( method == 'nltk' ):
        """
        Copied from NLTK package.
        Remove HTML markup from the given string.

        :param html: the HTML string to be cleaned
        :type html: str
        :rtype: str
        """

        # First we remove inline JavaScript/CSS:
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", html.strip())
        # Then we remove html comments. This has to be done before removing regular
        # tags since comments can contain '>' characters.
        cleaned = re.sub(r"(?s)<!--(.*?)-->[\n]?", "", cleaned)
        # Next we can remove the remaining tags:
        cleaned = re.sub(r"(?s)<.*?>", " ", cleaned)
        # Finally, we deal with whitespace
        cleaned = re.sub(r"&nbsp;", " ", cleaned)
        cleaned = re.sub(r"  ", " ", cleaned)
        cleaned = re.sub(r"  ", " ", cleaned)

        #my addition to remove blank lines
        cleaned = re.sub("\n\s*\n*", "\n", cleaned)

        return cleaned.strip()

    return ''

def extractFavIconFromHTML(html, sourceURL):
    
    sourceURL = sourceURL.strip()
    favicon = ''
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.findAll('link')
        breakFlag = False

        for link in links:
            if( link.has_attr('rel') ):
                for rel in link['rel']:
                    
                    rel = rel.lower().strip()
                    if( rel.find('icon') != -1 or rel.find('shortcut') != -1 ):
                        favicon = link['href'].strip()
                        breakFlag = True
                        break

            if( breakFlag ):
                break

        if( len(favicon) != 0 and len(sourceURL) != 0 ):
            if( favicon.find('//') == 0 ):
                favicon = 'http:' + favicon
            elif( favicon[0] == '/' ):
                scheme, netloc, path, params, query, fragment = urlparse( sourceURL )
                favicon = scheme + '://' + netloc + favicon
    except:
        genericErrorInfo()

    return favicon
#html/url - end

#text - start
def isExclusivePunct(text):

    text = text.strip()
    for char in text:
        if char not in string.punctuation:
            return False

    return True

def isStopword(term):

    stopWordsDict = getStopwordsDict()
    if( term.strip().lower() in stopWordsDict ):
        return True
    else:
        return False

def getStopwordsDict():

    stopwordsDict = {
        "a": True,
        "about": True,
        "above": True,
        "across": True,
        "after": True,
        "afterwards": True,
        "again": True,
        "against": True,
        "all": True,
        "almost": True,
        "alone": True,
        "along": True,
        "already": True,
        "also": True,
        "although": True,
        "always": True,
        "am": True,
        "among": True,
        "amongst": True,
        "amoungst": True,
        "amount": True,
        "an": True,
        "and": True,
        "another": True,
        "any": True,
        "anyhow": True,
        "anyone": True,
        "anything": True,
        "anyway": True,
        "anywhere": True,
        "are": True,
        "around": True,
        "as": True,
        "at": True,
        "back": True,
        "be": True,
        "became": True,
        "because": True,
        "become": True,
        "becomes": True,
        "becoming": True,
        "been": True,
        "before": True,
        "beforehand": True,
        "behind": True,
        "being": True,
        "below": True,
        "beside": True,
        "besides": True,
        "between": True,
        "beyond": True,
        "both": True,
        "but": True,
        "by": True,
        "can": True,
        "can\'t": True,
        "cannot": True,
        "cant": True,
        "co": True,
        "could not": True,
        "could": True,
        "couldn\'t": True,
        "couldnt": True,
        "de": True,
        "describe": True,
        "detail": True,
        "did": True,
        "do": True,
        "does": True,
        "doing": True,
        "done": True,
        "due": True,
        "during": True,
        "e.g": True,
        "e.g.": True,
        "e.g.,": True,
        "each": True,
        "eg": True,
        "either": True,
        "else": True,
        "elsewhere": True,
        "enough": True,
        "etc": True,
        "etc.": True,
        "even though": True,
        "ever": True,
        "every": True,
        "everyone": True,
        "everything": True,
        "everywhere": True,
        "except": True,
        "for": True,
        "former": True,
        "formerly": True,
        "from": True,
        "further": True,
        "get": True,
        "go": True,
        "had": True,
        "has not": True,
        "has": True,
        "hasn\'t": True,
        "hasnt": True,
        "have": True,
        "having": True,
        "he": True,
        "hence": True,
        "her": True,
        "here": True,
        "hereafter": True,
        "hereby": True,
        "herein": True,
        "hereupon": True,
        "hers": True,
        "herself": True,
        "him": True,
        "himself": True,
        "his": True,
        "how": True,
        "however": True,
        "i": True,
        "ie": True,
        "i.e": True,
        "i.e.": True,
        "if": True,
        "in": True,
        "inc": True,
        "inc.": True,
        "indeed": True,
        "into": True,
        "is": True,
        "it": True,
        "its": True,
        "it's": True,
        "itself": True,
        "just": True,
        "keep": True,
        "latter": True,
        "latterly": True,
        "less": True,
        "made": True,
        "make": True,
        "may": True,
        "me": True,
        "meanwhile": True,
        "might": True,
        "mine": True,
        "more": True,
        "moreover": True,
        "most": True,
        "mostly": True,
        "move": True,
        "must": True,
        "my": True,
        "myself": True,
        "namely": True,
        "neither": True,
        "never": True,
        "nevertheless": True,
        "next": True,
        "no": True,
        "nobody": True,
        "none": True,
        "noone": True,
        "nor": True,
        "not": True,
        "nothing": True,
        "now": True,
        "nowhere": True,
        "of": True,
        "off": True,
        "often": True,
        "on": True,
        "once": True,
        "one": True,
        "only": True,
        "onto": True,
        "or": True,
        "other": True,
        "others": True,
        "otherwise": True,
        "our": True,
        "ours": True,
        "ourselves": True,
        "out": True,
        "over": True,
        "own": True,
        "part": True,
        "per": True,
        "perhaps": True,
        "please": True,
        "put": True,
        "rather": True,
        "re": True,
        "same": True,
        "see": True,
        "seem": True,
        "seemed": True,
        "seeming": True,
        "seems": True,
        "several": True,
        "she": True,
        "should": True,
        "show": True,
        "side": True,
        "since": True,
        "sincere": True,
        "so": True,
        "some": True,
        "somehow": True,
        "someone": True,
        "something": True,
        "sometime": True,
        "sometimes": True,
        "somewhere": True,
        "still": True,
        "such": True,
        "take": True,
        "than": True,
        "that": True,
        "the": True,
        "their": True,
        "theirs": True,
        "them": True,
        "themselves": True,
        "then": True,
        "thence": True,
        "there": True,
        "thereafter": True,
        "thereby": True,
        "therefore": True,
        "therein": True,
        "thereupon": True,
        "these": True,
        "they": True,
        "this": True,
        "those": True,
        "though": True,
        "through": True,
        "throughout": True,
        "thru": True,
        "thus": True,
        "to": True,
        "together": True,
        "too": True,
        "toward": True,
        "towards": True,
        "un": True,
        "until": True,
        "upon": True,
        "us": True,
        "very": True,
        "via": True,
        "was": True,
        "we": True,
        "well": True,
        "were": True,
        "what": True,
        "whatever": True,
        "when": True,
        "whence": True,
        "whenever": True,
        "where": True,
        "whereafter": True,
        "whereas": True,
        "whereby": True,
        "wherein": True,
        "whereupon": True,
        "wherever": True,
        "whether": True,
        "which": True,
        "while": True,
        "whither": True,
        "who": True,
        "whoever": True,
        "whole": True,
        "whom": True,
        "whose": True,
        "why": True,
        "will": True,
        "with": True,
        "within": True,
        "without": True,
        "would": True,
        "yet": True,
        "you": True,
        "your": True,
        "yours": True,
        "yourself": True,
        "yourselves": True
    }
    
    return stopwordsDict

def getTokenLabelsForText(text, label):

    if( len(text) == 0 or len(label) == 0 ):
        return []

    labeledTokens = []
    text = re.findall(r'(?u)\b[a-zA-Z\'\’-]+[a-zA-Z]+\b|\d+[.,]?\d*', text)

    for tok in text:
        tok = tok.strip()
        
        if( tok == '' or isExclusivePunct(tok) is True or isStopword(tok) is True ):
            continue

        labeledTokens.append({ 'entity': tok, 'class': label })

    return labeledTokens

def getTopKTermsListFromText(textOrTokens, k, minusStopwords=True):

    if( len(textOrTokens) == 0 or k < 1 ):
        return []

    stopWordsDict = {}
    if( minusStopwords ):
        stopWordsDict = getStopwordsDict()

    topKTermDict = {}
    topKTermsList = []
    textOrTokens = textOrTokens.split(' ') if isinstance(textOrTokens, str) else textOrTokens

    for term in textOrTokens:
        term = term.strip().lower()
        
        if( len(term) == 0 or term in stopWordsDict or isExclusivePunct(term) == True ):
            continue

        topKTermDict.setdefault(term, 0)
        topKTermDict[term] += 1

    sortedKeys = sorted( topKTermDict, key=lambda freq:topKTermDict[freq], reverse=True )

    if( k > len(sortedKeys) ):
        k = len(sortedKeys)

    for i in range(k):
        key = sortedKeys[i]
        topKTermsList.append((key, topKTermDict[key]))

    return topKTermsList

def get_top_k_terms(text_or_tokens, k, class_name=''):    
    top_k_terms = getTopKTermsListFromText( text_or_tokens, k )
    if( class_name == '' ):
        return [{'entity': e[0], 'class': f'TOP_{k}_TERM'} for e in top_k_terms]
    else:
        return [{'entity': e[0], 'class': class_name} for e in top_k_terms]

def get_spacy_entities(spacy_ents, top_k_terms=[], base_ref_date=datetime.now(), labels_lst=[], **kwargs):
    
    kwargs.setdefault('output_2d_lst', False)
    '''
        #spacy entities: 
            nlp = spacy.load('en_core_web_sm')
            nlp.get_pipe("ner").labels
            ('ORG', 'EVENT', 'NORP', 'ORDINAL', 'LOC', 'FAC', 'DATE', 'WORK_OF_ART', 'TIME', 'GPE', 'LANGUAGE', 'LAW', 'QUANTITY', 'PRODUCT', 'PERCENT', 'CARDINAL', 'PERSON', 'MONEY')
    '''

    ents_dedup = set()
    final_ents = []
    
    for e in spacy_ents:

        ent_str = e.text
        if( labels_lst != [] and e.label_ not in labels_lst ):
            continue

        #normalize date - start
        if( e.label_ == 'DATE' ):
            
            parsed_date = parseDateStr( ent_str, settings={'RELATIVE_BASE': base_ref_date} )
            if( parsed_date is None ):
                continue

            ent_str = parsed_date.strftime('%Y-%m-%dT%H:%M:%S')
        #normalize date - end

        ent_key = ent_str.lower() + e.label_
        if( ent_key in ents_dedup ):
            continue

        ents_dedup.add(ent_key)
        if( kwargs['output_2d_lst'] is True ):
            final_ents.append( [ent_str, e.label_] )
        else:
            final_ents.append({ 'entity': ent_str, 'class': e.label_ })


    #add top k terms & avoid duplicates - start
    for e in top_k_terms:

        ent_key = e['entity'].lower() + e['class']
        if( ent_key in ents_dedup ):
            continue

        ents_dedup.add(ent_key)
        if( kwargs['output_2d_lst'] is True ):
            final_ents.append([ e['entity'], e['class'] ])
        else:
            final_ents.append({ 'entity': e['entity'], 'class': e['class'] })
    #add top k terms & avoid duplicates - end

    return final_ents

def parallel_ner(link, add_top_k_terms=10, min_doc_word_count=100):

    nlp = spacy.load('en_core_web_sm')
    spacy_doc = nlp( link['text'] )
    doc_len = len(spacy_doc)

    if( min_doc_word_count < 100 ):
        return {'entities': []}

    top_k_terms = get_top_k_terms( [t.text for t in spacy_doc], add_top_k_terms )
    if( 'title' in link ):
        top_k_terms += getTokenLabelsForText( link['title'], 'TITLE' )

    return { 
        'entities': get_spacy_entities(spacy_doc.ents, top_k_terms=top_k_terms, base_ref_date=datetime.now(), labels_lst=list(nlp.get_pipe('ner').labels), output_2d_lst=False)
    }

def parse_inpt_for_links(usr_input):

    def get_link(link_or_file):

        link_or_file = link_or_file.strip()
        if( link_or_file.startswith('http') ):
            return [{'link': link_or_file}]

        links = []
        with open(link_or_file, 'r') as infile:
            for l in infile:
        
                l = l.strip()
                if( l.startswith('http') ):
                    links.append({'link': l})
                elif( l.startswith('{') ):
                    
                    try:
                        l = json.loads(l)
                    except:
                        genericErrorInfo()
                        continue
                    
                    if( 'link' in l ):
                        links.append(l)
        
        return links

    all_link_details = []
    for link_or_file in usr_input:
        all_link_details += get_link(link_or_file)

    return all_link_details

def get_entities_frm_links(links, update_rate=10, **kwargs):
    
    warnings.filterwarnings("ignore",message="The localize method is no longer necessary, as this time zone supports the fold attribute")
    add_top_k_terms = kwargs.get('add_top_k_terms', 10)
    min_doc_word_count = kwargs.get('min_doc_word_count', 100)
    #rename for parallelGetTxtFrmURIs
    kwargs.setdefault('threadCount', kwargs.pop('thread_count', 5))
    
    jobs_lst = []
    links = parallelGetTxtFrmURIs(links, updateRate=update_rate, **kwargs)

    for i in range(len(links)):
        
        keywords = {
            'link': links[i],
            'add_top_k_terms': add_top_k_terms,
            'min_doc_word_count': min_doc_word_count
        }

        jobs_lst.append({
            'func': parallel_ner,
            'args': keywords,
            'misc': None,
            'print': ''
        })
    
    res_lst = parallelTask(jobs_lst, threadCount=kwargs['threadCount'])
    if( len(res_lst) == len(links) ):
        for i in range(len(links)):
            
            links[i]['link'] = links[i].pop('uri')
            links[i]['entities'] = res_lst[i]['output']['entities']

    return links

def sanitizeText(text):

    #UnicodeEncodeError: 'utf-8' codec can't encode character '\ud83d' in position 3507: surrogates not allowed
    try:
        text.encode('utf-8')
    except UnicodeEncodeError as e:
        if e.reason == 'surrogates not allowed':    
            text = text.encode('utf-8', 'backslashreplace').decode('utf-8')
    except:
        text = ''

    return text

#text - end