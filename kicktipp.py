import sys
import http.client
import urllib
import random
import math
from html.parser import HTMLParser
from userdata import user, password, runde

# set to True for enhanced output
DEBUG = False

COLS = [1, 2, 4, 5, 6, 7] # für EM tippspiel
# COLS = [1, 2, 3, 4, 5, 6] # für Bundesliga

def tipp(spiel):
    q = spiel['qheim'] / spiel['qgast']
    diff = int(round(math.log(q,1.9),0))
    h, g = 0, 0
    if diff > 0:
        h, g = 0, diff
    else:
        h, g = -diff, 0
    while random.randint(0,2) == 0:
        h += 1
        g += 1
    return h, g

spieltag = None if len(sys.argv) < 2 else sys.argv[1]

def debug(*msg):
    if(DEBUG):
        print(*msg)

def val(attrs, key):
    for attr in attrs:
        if attr[0] == key:
            return attr[1]
    return None

class TippFormParser(HTMLParser):
    _istable = False
    _colcount = 0
    _spiel = {}
    tipperid = None
    spieltag = None
    spiele = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and val(attrs,'id') == 'tippabgabeSpiele':
            debug('found table')
            self._istable = True
        elif tag =='input' and val(attrs,'id') == 'mitgliedIdHidden':
            debug('found tipperId')
            self.tipperid = val(attrs, 'value')
        elif tag =='input' and (val(attrs,'id') == 'spieltagIndex' or val(attrs,'name') == 'spieltagIndex'):
            debug('found spieltagindex')
            self.spieltag = val(attrs, 'value')
        elif self._istable:
            if tag == 'tr':
                self._colcount = -1
            elif tag == 'td':
                self._colcount += 1
            elif self._colcount == COLS[2] and tag == 'input' and val(attrs,'type') == 'hidden':
                name = val(attrs, 'name')
                debug('found spiel id')
                self._spiel['id'] = name[name.index('[')+1:name.index(']')]

    def handle_endtag(self, tag):
        if tag == 'table':
            debug('found table end')
            self._istable=False
        elif self._istable and tag =='tr' and 'id' in self._spiel:
            self.spiele.append(self._spiel)
            debug('found spiel', self._spiel)
            self._spiel = {}
            
    def handle_data(self, data):
        if self._istable:
            debug('col', self._colcount, data)
            if self._colcount == COLS[0]:
                self._spiel['heim'] = data
            elif self._colcount == COLS[1]:
                self._spiel['gast'] = data
            elif self._colcount == COLS[3] and data != '-':
                self._spiel['qheim'] = float(data)
            elif self._colcount == COLS[4] and data != '-':
                self._spiel['qremis'] = float(data)
            elif self._colcount == COLS[5] and data != '-':
                self._spiel['qgast'] = float(data)

class KickTippBrowser:
    def __init__(self):
        self._cookies = {}
        self._connection = http.client.HTTPSConnection('www.kicktipp.de')

    def _getcookies(self):
        res = ''
        for cookie in self._cookies.items():
            res = res + '; ' + cookie[0] + '=' + cookie[1]
        return res[2:]
        
    def _setcookie(self,cookie):
        cookie = cookie[:cookie.index(';')]
        i = cookie.index('=')
        self._cookies[cookie[:i]]=cookie[i+1:]

    def request(self,method, path, query = {}):
        headers = { 'Cookie': self._getcookies(), 'Accept': 'text/html' }
        fullpath = '/%s/%s?%s' % (runde, path, urllib.parse.urlencode(query))
        debug('requesting %s@%s' % (method, fullpath))
        self._connection.request(method, fullpath, None, headers)
        response = self._connection.getresponse()
        status = response.status
        debug('response %s' % status)
        data = response.read()
        for header in response.getheaders():
            if header[0] == 'Set-Cookie':
                self._setcookie(header[1])
        if status > 399:
            print('request %s@%s failed' % (method, path))
            print('error message: ' + data.decode())
            exit(1)
        return data
 
    def close(self):
        self._connection.close()

browser = KickTippBrowser()
browser.request('GET', 'profil/login')
browser.request('POST','profil/loginaction', {'kennung': user, 'passwort': password})
tippform = browser.request('GET', 'tippabgabe', {'spieltagIndex': spieltag} if spieltag else {})
parser = TippFormParser()
parser.feed(str(tippform, 'utf-8'))
debug(parser.tipperid)
debug(parser.spiele)
tipps = {'tipperId': parser.tipperid, 'spieltagIndex': parser.spieltag, 'bonus': 'false'}
for spiel in parser.spiele:
    formid = 'spieltippForms[%s].' % spiel['id']
    heim, gast = tipp(spiel)
    print('%d:%d %s - %s' % (heim, gast, spiel['heim'], spiel['gast']))
    tipps[formid+'tippAbgegeben'] = 'true'
    tipps[formid+'heimTipp'] = heim
    tipps[formid+'gastTipp'] = gast
browser.request('POST', 'tippabgabe', tipps)
browser.request('GET', 'profil/logout')
browser.close()
