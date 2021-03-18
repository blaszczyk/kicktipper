import sys
import http.client
import urllib
import random
import math
from html.parser import HTMLParser

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

properties = {}
with open('kicktipp.properties', 'rt') as propertiesfile:
    for line in propertiesfile:
        property = line.split('=')
        properties[property[0].strip()]=property[1].strip()

user = properties['user']
password = properties['password']
runde = properties['runde']

spieltag = None if len(sys.argv) < 2 else sys.argv[1]
debugenabled = False

def debug(msg):
    if(debugenabled):
        print(msg)

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
            self._istable = True
        elif tag =='input' and val(attrs,'id') == 'mitgliedIdHidden':
            self.tipperid = val(attrs, 'value')
        elif tag =='input' and val(attrs,'id') == 'spieltagIndex':
            self.spieltag = val(attrs, 'value')
        elif self._istable:
            if tag == 'tr':
                self._colcount = -1
            elif tag == 'td':
                self._colcount += 1
            elif self._colcount == 3 and tag == 'input' and val(attrs,'type') == 'hidden':
                name = val(attrs, 'name')
                self._spiel['id'] = name[name.index('[')+1:name.index(']')]

    def handle_endtag(self, tag):
        if tag == 'table':
            self._istable=False
        elif self._istable and tag =='tr' and 'id' in self._spiel:
            self.spiele.append(self._spiel)
            self._spiel = {}
            
    def handle_data(self, data):
        if self._istable:
            if self._colcount == 1:
                self._spiel['heim'] = data
            elif self._colcount == 2:
                self._spiel['gast'] = data
            elif self._colcount == 4:
                self._spiel['qheim'] = float(data)
            elif self._colcount == 5:
                self._spiel['qremis'] = float(data)
            elif self._colcount == 6:
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
