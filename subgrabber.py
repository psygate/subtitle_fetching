import requests
from bs4 import BeautifulSoup
import hashlib
import sys
import os
import time
import pprint
import json
import io
import zipfile

MAX_CACHE_AGE_SECONDS = 3600
CACHE_FOLDER = '.cache/'
USER_AGENT = 'subgrabber' #'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'

PP = pprint.PrettyPrinter(indent=4)

def request_and_cache(uri, cache_file_name):
    r = requests.get(uri, headers={
            'user-agent': USER_AGENT,
        })
    if r.status_code == requests.codes.ok:
        with open(cache_file_name, "wb") as f:
            f.write(r.content)
    else:
        raise ValueError("Request failed.")

    return r.content


def load_cached_file(uri, cache_file_name):
    with open(cache_file_name, "rb") as f:
        return f.read()


def request_or_load(uri, as_soup=True):
    m = hashlib.sha256()
    m.update(uri.encode("utf-8"))

    if not os.path.exists(CACHE_FOLDER):
        os.makedirs(CACHE_FOLDER, exist_ok=True)
    
    cache_file_name = os.path.join(CACHE_FOLDER, f'{m.hexdigest()}.csubgrabber')

    value = None
    
    if os.path.exists(cache_file_name) and time.time() - os.stat(cache_file_name).st_mtime < MAX_CACHE_AGE_SECONDS:
        value = load_cached_file(uri, cache_file_name)
    else:
        value = request_and_cache(uri, cache_file_name)

    if as_soup:
        return BeautifulSoup(value, 'html.parser')
    else:
        return value

def parse_movie_page(pagedict):
    
    try:
        data = dict()
        mp = pagedict['data']
        base = mp.find(itemtype='http://schema.org/Movie')
        
        data['title'] = base.find(class_='movie-main-title').contents
        data['genre'] = base.find(class_='movie-genre').contents
        data['subtitles'] = list()

        #subtable
        table = mp.find('table', class_='table other-subs')
        
        if table is None:
            return None
        else:
            subtitles = list()
            # Skip table header
            for row in table.find('tbody').find_all('tr'):
                
                subtitle_row = dict()
                lang = row.find('span', class_='sub-lang')

                if lang:
                    lang = lang.contents
                    subtitle_row['lang'] = lang

                linkcell = row.find('a', class_='subtitle-download')

                if linkcell:
                    subtitle_row['link'] = f'{pagedict["base_uri"]}{linkcell["href"]}'

                subtitles.append(subtitle_row)

            data['subtitle_links'] = subtitles
                        
            return data
    except:
        raise ValueError(f'Cant parse: {pagedict["uri"]}')


def extract_subtitle_files(subdata):
    zipdata = io.BytesIO(subdata)
    zf = zipfile.ZipFile(zipdata)
    subs = list()
    for name in zf.namelist():
        if(name.endswith(".srt")):
            with zf.open(name) as subentry:
                data = subentry.read()
                subs.append(data)

    return subs

def fetch_subtitles(movies, languages):
    for movie in movies:
        links = movie['subtitle_links']
        for subitem in links:
            language_list = subitem['lang']
            if any((x in languages for x in language_list)):
                subpage = request_or_load(subitem['link'])
                sublink = subpage.find('a', class_='download-subtitle')["href"]
                subdata = request_or_load(sublink, as_soup=False)

                subs = extract_subtitle_files(subdata)
                subitem['subtitles'] = subs

    return movies



def main():
    languages = ['English']
    movies = list()
    base_uri = 'http://www.yifysubtitles.com'

    for pagenum in range(10):
        soup = request_or_load(f'{base_uri}/browse/page-{pagenum}')

        for ul in soup.find_all(class_='media-list'):
            li = ul.find_all('li')
            bodies = [elem.find(class_='media-body') for elem in li]
            anchors = [body.find('a') for body in bodies if body is not None]
            refs = [anchor['href'] for anchor in anchors]
            
            movie_pages = [{'uri': f'{base_uri}{ref}', 'data': request_or_load(f'{base_uri}{ref}'), 'base_uri': base_uri} for ref in refs]
            lmovies = [x for x in [parse_movie_page(page) for page in movie_pages if page is not None] if x is not None]
            
            movies += lmovies

    with_subs = fetch_subtitles(movies, languages)
    PP.pprint(with_subs)


if __name__ == '__main__':
    main()
