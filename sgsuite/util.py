import os
import json
import logging
import requests
import sys

from datetime import datetime
from multiprocessing import Pool
from subprocess import check_output
from time import sleep
from urllib.parse import urlparse

from boilerpy3 import extractors

from bs4 import BeautifulSoup
from tldextract import extract as extract_tld

logger = logging.getLogger('sgsuite.sgsuite')

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

#parallel proc - start
def parallelProxy(job):
    
    output = job['func'](**job['args'])

    if( 'print' in job ):
        if( len(job['print']) != 0 ):
            
            logger.info( job['print'] )

    return {'input': job, 'output': output, 'misc': job['misc']}

def parallelTask(jobsLst, threadCount=5):

    if( len(jobsLst) == 0 ):
        return []

    if( threadCount < 2 ):
        threadCount = 2

    try:
        workers = Pool(threadCount)
        resLst = workers.map(parallelProxy, jobsLst)

        workers.close()
        workers.join()
    except:
        logger.error( genericErrorInfo() )
        return []

    return resLst
#parallel proc - end